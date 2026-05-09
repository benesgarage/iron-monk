import dataclasses
import functools
import inspect
import types
from typing import (
    TypeVar,
    Any,
    Callable,
    Iterable,
    AsyncIterable,
    AsyncIterator,
    Iterator,
    Mapping,
    cast,
    get_origin,
    get_args,
    get_type_hints,
    Union,
)
from .exceptions import ValidationError, MissingContextError
from .types import ErrorDict
from .config import settings
from .protocols import MonkConstraint

T = TypeVar("T")

_PRIMITIVE_TYPES = frozenset((str, int, float, bool, type(None)))

_UNION_TYPES: tuple[Any, ...] = (Union, types.UnionType)

_CONTAINER_ORIGINS: tuple[Any, ...] = (list, set, frozenset, tuple, dict)

_USER_CONTAINER_CONSTRAINT_NAMES: frozenset[str] = frozenset(("Each", "DictOf", "_TupleSchema"))

# Module-level fast bindings for hot paths
_obj_ga = object.__getattribute__
_obj_sa = object.__setattr__


def _make_resolver(instance: Any) -> Callable[[str], Any]:
    """Builds a sibling-field resolver bound to a specific dataclass instance."""

    def _resolver(target_name: str) -> Any:
        try:
            return _obj_ga(instance, target_name)
        except AttributeError:
            return None

    return _resolver


def _format_constraint_message(c: Any, value: Any, default_msg: str) -> str:
    """Formats `c.message` with field/value context (matches `@constraint` wrapper).

    Used by hot paths that bypass the wrapper via `_validate_inner` and must
    apply custom message templates manually when an exception is caught.
    """
    custom = getattr(c, "message", None)
    if custom is None:
        return default_msg
    ctx: dict[str, Any] = {"value": value}
    if dataclasses.is_dataclass(c):
        for f in dataclasses.fields(c):
            ctx[f.name] = getattr(c, f.name)
    try:
        return cast(str, custom.format(**ctx))
    except Exception:
        return cast(str, custom)


class _RefBlueprint:
    """A mapping of where Refs live inside a constraint tree."""

    __slots__ = ("refs", "clone_attrs", "nested")

    def __init__(self, refs: dict[str, Any], clone_attrs: tuple[str, ...], nested: dict[str, Any]) -> None:
        self.refs = refs
        self.clone_attrs = clone_attrs
        self.nested = nested


def _build_blueprint(constraint: Any) -> _RefBlueprint | None:
    """Walks a constraint tree and compiles a blueprint"""
    has_refs = False
    refs = {}
    attrs_to_copy = []
    for field_name in dir(constraint):
        if field_name.startswith("__"):
            continue
        try:
            value = getattr(constraint, field_name)
            # Prevent copying bound methods which permanently bind 'self' to the original instance
            if inspect.ismethod(value) and getattr(value, "__self__", None) is constraint:
                continue
            attrs_to_copy.append(field_name)
            if type(value).__name__ in ("Ref", "Ctx"):
                refs[field_name] = value
                has_refs = True
        except AttributeError:
            pass

    # Check known nested constraint fields (like DictOf, CSV, AnyOf, Not, When, etc.)
    nested: dict[str, Any] = {}
    for nested_attr in (
        "constraints",
        "_key_constraints",
        "_value_constraints",
        "_prepared",
        "constraint",
        "test",
        "then",
        "else_",
        "default",
    ):
        if hasattr(constraint, nested_attr):
            val = getattr(constraint, nested_attr)
            if isinstance(val, (tuple, list)):
                child_blueprints = []
                for inner_constraint in val:
                    child_blueprints.append(_build_blueprint(inner_constraint))
                if any(blueprint is not None for blueprint in child_blueprints):
                    nested[nested_attr] = tuple(child_blueprints)
                    has_refs = True
            elif hasattr(val, "validate"):
                blueprint = _build_blueprint(val)
                if blueprint is not None:
                    nested[nested_attr] = blueprint
                    has_refs = True

    # Gather blueprints from Unions
    if isinstance(constraint, _UnionRouter):
        new_value_blueprints = []
        for _, branch_constraints in constraint.union_branches:
            branch_blueprints = []
            for _, inner_blueprint in branch_constraints:
                branch_blueprints.append(inner_blueprint)
                if inner_blueprint is not None:
                    has_refs = True
            new_value_blueprints.append(tuple(branch_blueprints))
        if has_refs:
            nested["union_branches"] = tuple(new_value_blueprints)

    if has_refs:
        return _RefBlueprint(refs, tuple(attrs_to_copy), nested)
    return None


def _execute_blueprint(
    constraint: Any,
    blueprint: _RefBlueprint,
    get_val: Callable[[str], Any],
    get_ctx: Callable[[str], Any] | None = None,
) -> Any:
    """
    Clones a constraint and maps Ref / Ctx values using the compiled blueprint.

    ``get_val`` resolves ``Ref(field_name)`` markers from sibling fields/args.
    ``get_ctx`` resolves ``Ctx(key)`` markers from a user-supplied context
    mapping. If a Ctx marker is present but ``get_ctx`` is None, a
    ``MissingContextError`` is raised (programmer error). If the key is
    absent from the provided context, a ``ValidationError`` is raised so the
    caller can aggregate it with other field errors.
    """
    cloned_constraint = type(constraint).__new__(type(constraint))  # type: ignore[call-overload]

    for attr_name in blueprint.clone_attrs:
        _obj_sa(cloned_constraint, attr_name, getattr(constraint, attr_name))

    unwrap = settings.unwrap
    for attr_name, marker in blueprint.refs.items():
        if type(marker).__name__ == "Ctx":
            if get_ctx is None:
                raise MissingContextError(
                    f"Constraint references Ctx({marker.key!r}) but no context= was passed to validate()."
                )
            try:
                resolved_val = unwrap(get_ctx(marker.key))
            except KeyError:
                raise ValidationError(
                    [
                        {
                            "field": "",
                            "message": f"Required context key '{marker.key}' is missing.",
                            "code": "MissingContextKey",
                        }
                    ]
                ) from None
        else:
            resolved_val = unwrap(get_val(marker.field_name))
        _obj_sa(cloned_constraint, attr_name, resolved_val)

    for nested_attr, nested_blueprint in blueprint.nested.items():
        if nested_attr == "union_branches":
            val = getattr(cloned_constraint, nested_attr)
            new_val = []
            for (branch_type, branch_constraints), branch_blueprints in zip(val, nested_blueprint):
                new_constraint = []
                for (inner_constraint, _), inner_blueprint in zip(branch_constraints, branch_blueprints):
                    if inner_blueprint is not None:
                        new_constraint.append(
                            (_execute_blueprint(inner_constraint, inner_blueprint, get_val, get_ctx), None)
                        )
                    else:
                        new_constraint.append((inner_constraint, None))
                new_val.append((branch_type, new_constraint))
            _obj_sa(cloned_constraint, nested_attr, new_val)
            continue

        val = getattr(cloned_constraint, nested_attr)
        if isinstance(val, tuple):
            new_val_tuple = tuple(
                _execute_blueprint(inner_constraint, inner_blueprint, get_val, get_ctx)
                if inner_blueprint
                else inner_constraint
                for inner_constraint, inner_blueprint in zip(val, nested_blueprint)
            )
            _obj_sa(cloned_constraint, nested_attr, new_val_tuple)
        elif isinstance(val, list):
            new_val_list = [
                _execute_blueprint(inner_constraint, inner_blueprint, get_val, get_ctx)
                if inner_blueprint
                else inner_constraint
                for inner_constraint, inner_blueprint in zip(val, nested_blueprint)
            ]
            _obj_sa(cloned_constraint, nested_attr, new_val_list)
        else:
            new_val_single = _execute_blueprint(val, nested_blueprint, get_val, get_ctx)
            _obj_sa(cloned_constraint, nested_attr, new_val_single)

    return cloned_constraint


class _UnionRouter(MonkConstraint):
    """An internal constraint used to route and evaluate Union branches."""

    def __init__(self, union_branches: list[tuple[Any, list[tuple[MonkConstraint, _RefBlueprint | None]]]]) -> None:
        self.union_branches = union_branches
        self._branch_origins: tuple[Any, ...] = tuple((get_origin(bt) or bt) for bt, _ in union_branches)
        self.code = "Union"

    def validate(self, value: Any) -> None:
        errors: list[Exception] = []
        origins = self._branch_origins
        for idx, branch_pair in enumerate(self.union_branches):
            branch = branch_pair[1]
            origin = origins[idx]
            if origin is not Any:
                try:
                    if not isinstance(value, origin):
                        continue
                except TypeError:
                    pass

            if not branch:
                return

            branch_passed = True
            for constraint_obj, _ in branch:
                fn = getattr(constraint_obj, "_validate_inner", None) or constraint_obj.validate
                try:
                    fn(value)
                except ValidationError as e:
                    errors.append(e)
                    branch_passed = False
                    break
                except (ValueError, TypeError) as e:
                    msg = _format_constraint_message(constraint_obj, value, str(e))
                    error_code = getattr(constraint_obj, "code", None) or type(constraint_obj).__name__
                    errors.append(ValidationError([{"field": "", "message": msg, "code": error_code}]))
                    branch_passed = False
                    break
            if branch_passed:
                return

        if len(errors) == 1:
            raise errors[0]

        raise ValueError("Value did not match any of the allowed union branches. Must satisfy at least one.")


class _TupleSchema(MonkConstraint):
    """Internal constraint that validates fixed-length heterogeneous tuples by applying
    per-position rules synthesized from `tuple[A, B, C]` style hints."""

    __slots__ = ("validators", "expected_len", "code")

    def __init__(self, validators: list[tuple[list[MonkConstraint], bool] | None]) -> None:
        self.validators = validators
        self.expected_len = len(validators)
        self.code = "TupleSchema"

    def validate(self, value: Any) -> None:
        if not isinstance(value, tuple):
            raise TypeError(f"Type '{type(value).__name__}' is not a tuple.")
        if len(value) != self.expected_len:
            raise ValueError(f"Tuple length must be {self.expected_len}, got {len(value)}.")

        errors: list[ErrorDict] = []
        for i, (raw_item, rule) in enumerate(zip(value, self.validators)):
            if rule is None:
                continue
            constraints, allow_none = rule
            item = settings.unwrap(raw_item)
            if item is None:
                if allow_none:
                    continue
                errors.append(
                    {"field": f"[{i}]", "message": "Field is required and cannot be null.", "code": "NotNull"}
                )
                continue
            for c in constraints:
                try:
                    c.validate(item)
                except ValidationError as e:
                    for err in e.errors:
                        err["field"] = f"[{i}]{err.get('field', '')}"
                        errors.append(err)
                except (ValueError, TypeError) as e:
                    error_code = getattr(c, "code", None) or type(c).__name__
                    errors.append({"field": f"[{i}]", "message": str(e), "code": error_code})

        if errors:
            raise ValidationError(errors)


def _prepare_constraints(
    constraints: Iterable[Any],
) -> tuple[list[tuple[MonkConstraint, _RefBlueprint | None]], bool, bool, Any]:
    """Takes raw constraints and compiles them into a highly optimized validation tuple."""
    actual_constraints: list[tuple[MonkConstraint, _RefBlueprint | None]] = []
    is_nullable = False
    is_not_null = False
    not_null_constraint = None

    for constraint_item in constraints:
        if isinstance(constraint_item, type) and issubclass(constraint_item, MonkConstraint):
            try:
                constraint_item = constraint_item()
            except TypeError as e:
                raise TypeError(
                    f"Constraint '{constraint_item.__name__}' missing required arguments. Did you mean {constraint_item.__name__}(...)?"
                ) from e

        if not isinstance(constraint_item, MonkConstraint):
            continue

        constraint_name = type(constraint_item).__name__
        if constraint_name == "Nullable":
            is_nullable = True
        elif constraint_name == "NotNull":
            is_not_null = True
            not_null_constraint = constraint_item
        else:
            blueprint = _build_blueprint(constraint_item)
            actual_constraints.append((constraint_item, blueprint))

    return actual_constraints, is_nullable, is_not_null, not_null_constraint


def _has_outer_container_synth(metadata: Iterable[Any]) -> bool:
    """Returns True when user already provided an Each/DictOf-style outer constraint,
    so auto-synthesis must skip to avoid double validation."""
    for m in metadata:
        cls = m if isinstance(m, type) else type(m)
        if cls.__name__ in _USER_CONTAINER_CONSTRAINT_NAMES:
            return True
    return False


def _compile_inner_validator(arg: Any) -> tuple[list[MonkConstraint], bool] | None:
    """Compile a type-hint argument (element/branch type) into per-value constraints
    plus an `allow_none` flag. Returns None when no validation is needed."""
    type_meta_map = getattr(settings, "type_metadata", {})

    metadata = list(getattr(arg, "__metadata__", []))
    base = arg
    if metadata:
        peeled = get_args(arg)
        if peeled:
            base = peeled[0]

    base_origin = get_origin(base)
    base_args = get_args(base)

    extra = type_meta_map.get(base_origin or base, [])
    if extra:
        metadata = metadata + list(extra)

    constraints: list[MonkConstraint] = []
    allow_none = False

    if metadata:
        prepared, is_nullable, _, _ = _prepare_constraints(metadata)
        constraints.extend(c for c, _ in prepared)
        allow_none = allow_none or is_nullable

    if base_origin in _UNION_TYPES:
        branches: list[tuple[Any, list[tuple[MonkConstraint, _RefBlueprint | None]]]] = []
        any_branch_has_constraints = False
        for branch in base_args:
            if branch is type(None):
                allow_none = True
                continue

            branch_compiled = _compile_inner_validator(branch)

            branch_type: Any = branch
            if getattr(branch, "__metadata__", None):
                bargs = get_args(branch)
                if bargs:
                    branch_type = bargs[0]
            b_origin = get_origin(branch_type)
            if b_origin is not None:
                branch_type = b_origin

            if branch_compiled is not None:
                branch_constraints, branch_nullable = branch_compiled
                allow_none = allow_none or branch_nullable
                prepared_branch = [(c, _build_blueprint(c)) for c in branch_constraints]
                if prepared_branch:
                    any_branch_has_constraints = True
                branches.append((branch_type, prepared_branch))
            else:
                branches.append((branch_type, []))

        if any_branch_has_constraints:
            constraints.append(_UnionRouter(branches))

    elif base_origin in _CONTAINER_ORIGINS:
        nested = _synthesize_container_constraint(base)
        if nested is not None:
            constraints.append(nested)

    if not constraints and not allow_none:
        return None
    return constraints, allow_none


def _synthesize_container_constraint(hint: Any) -> MonkConstraint | None:
    """Build an Each / DictOf / _TupleSchema from a container hint whose inner args
    carry Annotated/Union validation. Returns None when nothing to enforce."""
    origin = get_origin(hint)
    args = get_args(hint)
    if origin not in _CONTAINER_ORIGINS or not args:
        return None

    # Lazy import: constraints.py → decorators.py → operations.py would cycle at module load.
    from .constraints import Each, DictOf, Nullable

    if origin is dict:
        if len(args) != 2:
            return None
        key_compiled = _compile_inner_validator(args[0])
        val_compiled = _compile_inner_validator(args[1])
        if key_compiled is None and val_compiled is None:
            return None
        key_constraints = key_compiled[0] if key_compiled else None
        val_constraints = val_compiled[0] if val_compiled else None
        if not key_constraints and not val_constraints:
            return None
        return DictOf(
            key=key_constraints if key_constraints else None,
            value=val_constraints if val_constraints else None,
        )

    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            inner = _compile_inner_validator(args[0])
            if inner is None:
                return None
            inner_constraints, inner_allow_none = inner
            if not inner_constraints:
                return None
            each_args: list[Any] = list(inner_constraints)
            if inner_allow_none:
                each_args.append(Nullable)
            return Each(*each_args)

        positional: list[tuple[list[MonkConstraint], bool] | None] = []
        for a in args:
            if type(a).__name__ in ("TypeVarTuple", "Unpack"):
                return None
            try:
                positional.append(_compile_inner_validator(a))
            except Exception:
                return None
        if not any(p is not None for p in positional):
            return None
        return _TupleSchema(positional)

    inner = _compile_inner_validator(args[0])
    if inner is None:
        return None
    inner_constraints, inner_allow_none = inner
    if not inner_constraints:
        return None
    each_args = list(inner_constraints)
    if inner_allow_none:
        each_args.append(Nullable)
    return Each(*each_args)


def _extract_monk_metadata(
    hints: dict[str, Any],
) -> dict[str, tuple[list[tuple[MonkConstraint, _RefBlueprint | None]], bool, bool, bool, Any]]:
    """Extracts validation rules from type hints into highly optimized structures."""
    rules: dict[str, tuple[list[tuple[MonkConstraint, _RefBlueprint | None]], bool, bool, bool, Any]] = {}
    type_meta_map = getattr(settings, "type_metadata", {})

    for name, hint in hints.items():
        metadata = getattr(hint, "__metadata__", [])
        extra_meta = type_meta_map.get(get_origin(hint) or hint, [])

        container_target = hint
        if metadata:
            peeled_outer = get_args(hint)
            if peeled_outer:
                container_target = peeled_outer[0]
        if get_origin(container_target) in _CONTAINER_ORIGINS:
            if not _has_outer_container_synth(list(metadata) + list(extra_meta)):
                synthesized = _synthesize_container_constraint(container_target)
                if synthesized is not None:
                    extra_meta = list(extra_meta) + [synthesized]

        if not metadata:
            args = get_args(hint)
            origin = get_origin(hint)

            if args and origin not in (list, set, frozenset, tuple, dict) and origin not in _UNION_TYPES:
                hint = args[0]
                metadata = getattr(hint, "__metadata__", [])
                args = get_args(hint)
                origin = get_origin(hint)

                inner_extra = type_meta_map.get(origin or hint, [])
                if inner_extra:
                    extra_meta = list(extra_meta) + list(inner_extra)

            if origin in _UNION_TYPES:
                branches: list[tuple[Any, list[tuple[MonkConstraint, _RefBlueprint | None]]]] = []
                is_outer_nullable = False
                is_inner_nullable = False
                is_not_null_global = False
                global_not_null_constraint = None

                for arg in args:
                    if arg is type(None):
                        is_outer_nullable = True
                        continue

                    arg_type = arg
                    arg_metadata: Any = getattr(arg, "__metadata__", [])

                    if not arg_metadata:
                        inner_args = get_args(arg)
                        inner_origin = get_origin(arg)
                        if inner_origin in _CONTAINER_ORIGINS:
                            synth_branch = _synthesize_container_constraint(arg)
                            if synth_branch is not None:
                                arg_metadata = [synth_branch]
                            arg_type = inner_origin
                        elif inner_args and inner_origin not in _UNION_TYPES:
                            arg_type = inner_args[0]
                            for inner_arg in inner_args:
                                inner_metadata = getattr(inner_arg, "__metadata__", [])
                                if inner_metadata:
                                    arg_metadata = inner_metadata
                                    break

                    if getattr(arg_type, "__metadata__", None):
                        base_args = get_args(arg_type)
                        if base_args:
                            arg_type = base_args[0]

                    arg_extra_meta = type_meta_map.get(get_origin(arg) or arg, [])
                    if arg_extra_meta:
                        arg_metadata = list(arg_metadata) + list(arg_extra_meta)

                    if arg_metadata:
                        constraint_list, parsed_nullable, parsed_not_null, parsed_not_null_constraint = (
                            _prepare_constraints(arg_metadata)
                        )
                        if parsed_nullable:
                            is_inner_nullable = True
                        if parsed_not_null:
                            is_not_null_global = True
                            global_not_null_constraint = parsed_not_null_constraint
                        branches.append((arg_type, constraint_list))
                    else:
                        branches.append((arg_type, []))

                non_empty_branches = [branch for branch in branches if branch[1]]
                if not non_empty_branches:
                    compiled_rules: tuple[
                        list[tuple[MonkConstraint, _RefBlueprint | None]], bool, bool, bool, Any | None
                    ] = (
                        [],
                        is_outer_nullable,
                        is_inner_nullable,
                        is_not_null_global,
                        global_not_null_constraint,
                    )
                elif len(branches) == 1:
                    compiled_rules = (
                        branches[0][1],
                        is_outer_nullable,
                        is_inner_nullable,
                        is_not_null_global,
                        global_not_null_constraint,
                    )
                else:
                    union_router = _UnionRouter(branches)
                    blueprint = _build_blueprint(union_router)
                    compiled_rules = (
                        [(union_router, blueprint)],
                        is_outer_nullable,
                        is_inner_nullable,
                        is_not_null_global,
                        global_not_null_constraint,
                    )

                if extra_meta:
                    extra_constraints, extra_is_nullable, extra_is_not_null, extra_not_null_constraint = (
                        _prepare_constraints(extra_meta)
                    )
                    constraint_list = compiled_rules[0] + extra_constraints
                    nullable_outer = compiled_rules[1]
                    nullable_inner = compiled_rules[2] or extra_is_nullable
                    not_null = compiled_rules[3] or extra_is_not_null
                    not_null_constraint = extra_not_null_constraint if extra_is_not_null else compiled_rules[4]
                    compiled_rules = (constraint_list, nullable_outer, nullable_inner, not_null, not_null_constraint)

                if compiled_rules[0] or compiled_rules[1] or compiled_rules[2] or compiled_rules[3]:
                    rules[name] = compiled_rules
                continue

        if extra_meta:
            metadata = list(metadata) + list(extra_meta)

        if metadata:
            constraint_list, parsed_nullable, parsed_not_null, parsed_not_null_constraint = _prepare_constraints(
                metadata
            )
            compiled_rules = (
                constraint_list,
                parsed_nullable,
                parsed_nullable,
                parsed_not_null,
                parsed_not_null_constraint,
            )
            # Only store it if there are actual constraints or nullability overrides
            if compiled_rules[0] or compiled_rules[1] or compiled_rules[3]:
                rules[name] = compiled_rules

    return rules


def _recurse(val: Any, prefix: str, errors: list[ErrorDict], context: Mapping[str, Any] | None = None) -> None:
    """Recursively validates nested Monk objects and bubbles up errors."""
    val = settings.unwrap(val)
    # getattr(..., None) is faster than hasattr + getattr
    if getattr(val, "__monk_rules__", None) is not None:
        try:
            validate(val, context=context)
        except ValidationError as e:
            for err in e.errors:
                err["field"] = f"{prefix}.{err['field']}"
                errors.append(err)
        return

    # Exact type checking is significantly faster than isinstance abstract base class checks
    val_type = type(val)
    primitives = _PRIMITIVE_TYPES
    if val_type is list or val_type is tuple:
        for i, item in enumerate(val):
            if type(item) not in primitives:
                _recurse(item, f"{prefix}[{i}]", errors, context)
    elif val_type is dict:
        for key, value in val.items():
            if type(value) not in primitives:
                _recurse(value, f"{prefix}[{repr(key)}]", errors, context)
    elif val_type is set or val_type is frozenset:  # Cannot be indexed
        for item in val:
            if type(item) not in primitives:
                _recurse(item, prefix, errors, context)


def validate_arguments(
    arguments: dict[str, Any],
    rules: dict[str, tuple[list[tuple[MonkConstraint, _RefBlueprint | None]], bool, bool, bool, Any]],
) -> None:
    """Validates a dictionary of function arguments against extracted constraints."""
    errors: list[ErrorDict] = []
    unwrap = settings.unwrap
    default_allow_none = settings.default_allow_none
    primitives = _PRIMITIVE_TYPES

    for arg_name, raw_value in arguments.items():
        rule_tuple = rules.get(arg_name)
        if rule_tuple:
            constraints, is_outer_nullable, is_inner_nullable, is_not_null, not_null_constraint = rule_tuple

            if raw_value is None:
                if not is_outer_nullable and (is_not_null or not default_allow_none):
                    msg = getattr(not_null_constraint, "message", None) or "Field is required and cannot be null."
                    code = getattr(not_null_constraint, "code", None) or "NotNull"
                    errors.append({"field": arg_name, "message": msg, "code": code})
                continue

            value = unwrap(raw_value)

            if value is None:
                if not is_inner_nullable and (is_not_null or not default_allow_none):
                    msg = getattr(not_null_constraint, "message", None) or "Field is required and cannot be null."
                    code = getattr(not_null_constraint, "code", None) or "NotNull"
                    errors.append({"field": arg_name, "message": msg, "code": code})
                continue

            for constraint_obj, blueprint in constraints:
                if blueprint is not None:
                    constraint_to_validate = _execute_blueprint(constraint_obj, blueprint, arguments.get)
                    # Cloned constraints have ephemeral ids — bypass cache to avoid leak.
                    fn = getattr(constraint_to_validate, "_validate_inner", None) or constraint_to_validate.validate
                else:
                    fn = getattr(constraint_obj, "_validate_inner", None) or constraint_obj.validate
                try:
                    fn(value)
                except ValidationError as e:
                    for error_dict in e.errors:
                        error_dict["field"] = f"{arg_name}{error_dict.get('field', '')}"
                        errors.append(error_dict)
                except (ValueError, TypeError) as e:
                    msg = _format_constraint_message(constraint_obj, value, str(e))
                    error_code = getattr(constraint_obj, "code", None) or type(constraint_obj).__name__
                    errors.append({"field": arg_name, "message": msg, "code": error_code})

            if type(value) not in primitives:
                _recurse(value, arg_name, errors)
        else:
            value = unwrap(raw_value)
            if type(value) not in primitives:
                _recurse(value, arg_name, errors)

    if errors:
        raise ValidationError(errors)


def validate_return(
    raw_value: Any, rule_tuple: tuple[list[tuple[MonkConstraint, _RefBlueprint | None]], bool, bool, bool, Any]
) -> None:
    """Validates a function's return value against extracted constraints."""
    errors: list[ErrorDict] = []
    constraints, is_outer_nullable, is_inner_nullable, is_not_null, not_null_constraint = rule_tuple

    if raw_value is None:
        if not is_outer_nullable and (is_not_null or not settings.default_allow_none):
            msg = getattr(not_null_constraint, "message", None) or "Field is required and cannot be null."
            code = getattr(not_null_constraint, "code", None) or "NotNull"
            errors.append({"field": "return", "message": msg, "code": code})
    else:
        value = settings.unwrap(raw_value)
        if value is None:
            if not is_inner_nullable and (is_not_null or not settings.default_allow_none):
                msg = getattr(not_null_constraint, "message", None) or "Field is required and cannot be null."
                code = getattr(not_null_constraint, "code", None) or "NotNull"
                errors.append({"field": "return", "message": msg, "code": code})
        else:
            for constraint_obj, _ in constraints:
                # Returns have no sibling fields, so we safely ignore blueprints.
                fn = getattr(constraint_obj, "_validate_inner", None) or constraint_obj.validate
                try:
                    fn(value)
                except ValidationError as e:
                    for error_dict in e.errors:
                        error_dict["field"] = f"return{error_dict.get('field', '')}"
                        errors.append(error_dict)
                except (ValueError, TypeError) as e:
                    msg = _format_constraint_message(constraint_obj, value, str(e))
                    error_code = getattr(constraint_obj, "code", None) or type(constraint_obj).__name__
                    errors.append({"field": "return", "message": msg, "code": error_code})

            if type(value) not in _PRIMITIVE_TYPES:
                _recurse(value, "return", errors)

    if errors:
        raise ValidationError(errors)


@functools.lru_cache(maxsize=None)
def _get_schema_rules(
    schema: type,
) -> tuple[set[str], dict[str, tuple[list[tuple[MonkConstraint, _RefBlueprint | None]], bool, bool, bool, Any]]]:
    """Caches the allowed keys and extracted rules for a given TypedDict schema to maximize performance."""
    hints = get_type_hints(schema, include_extras=True)
    return set(hints.keys()), _extract_monk_metadata(hints)


def validate_dict(
    data: dict[str, Any],
    schema: type,
    *,
    partial: bool = False,
    drop_extra_keys: bool = False,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validates a raw dictionary against a TypedDict or Dataclass schema without instantiating an object.

    Args:
        data (dict[str, Any]): The raw dictionary payload to validate.
        schema (type): The TypedDict or Dataclass schema containing the validation rules.
        partial (bool, optional): If True, ignores keys that are missing from the payload (useful for PATCH requests). Defaults to False.
        drop_extra_keys (bool, optional): If True, strips any keys not explicitly defined in the schema. Defaults to False.
        context (Mapping[str, Any] | None, optional): Read-only mapping used to resolve
            ``Ctx(key)`` markers inside constraints. Defaults to None.

    Returns:
        dict[str, Any]: The validated (and optionally sanitized) dictionary.

    Raises:
        ValidationError: If the dictionary fails any validation constraints or contains unrecognized keys (when drop_extra_keys is False).
        MissingContextError: If a constraint references ``Ctx(...)`` but no context was provided.
    """
    allowed_keys, rules = _get_schema_rules(schema)
    errors: list[ErrorDict] = []
    unwrap = settings.unwrap
    default_allow_none = settings.default_allow_none
    ctx_resolver: Callable[[str], Any] | None = context.__getitem__ if context is not None else None

    if not drop_extra_keys:
        # Using data.keys() view is much faster than instantiating a new set() object
        extra_keys = data.keys() - allowed_keys
        if extra_keys:
            errors.append(
                {
                    "field": "__root__",
                    "message": f"Unrecognized fields provided: {', '.join(sorted(extra_keys))}",
                    "code": "StrictDictionary",
                }
            )

    for field_name, rule_tuple in rules.items():
        if partial and field_name not in data:
            continue

        raw_value = data.get(field_name)
        constraints, is_outer_nullable, is_inner_nullable, is_not_null, not_null_constraint = rule_tuple

        if raw_value is None:
            if not is_outer_nullable and (is_not_null or not default_allow_none):
                msg = getattr(not_null_constraint, "message", None) or "Field is required and cannot be null."
                code = getattr(not_null_constraint, "code", None) or "NotNull"
                errors.append({"field": field_name, "message": msg, "code": code})
            continue

        value = unwrap(raw_value)

        if value is None:
            if not is_inner_nullable and (is_not_null or not default_allow_none):
                msg = getattr(not_null_constraint, "message", None) or "Field is required and cannot be null."
                code = getattr(not_null_constraint, "code", None) or "NotNull"
                errors.append({"field": field_name, "message": msg, "code": code})
            continue

        for constraint_obj, blueprint in constraints:
            if blueprint is not None:
                try:
                    constraint_to_validate = _execute_blueprint(constraint_obj, blueprint, data.get, ctx_resolver)
                except ValidationError as e:
                    for error_dict in e.errors:
                        error_dict["field"] = f"{field_name}{error_dict.get('field', '')}"
                        errors.append(error_dict)
                    continue
                fn = getattr(constraint_to_validate, "_validate_inner", None) or constraint_to_validate.validate
            else:
                fn = getattr(constraint_obj, "_validate_inner", None) or constraint_obj.validate
            try:
                fn(value)
            except ValidationError as e:
                for error_dict in e.errors:
                    error_dict["field"] = f"{field_name}{error_dict.get('field', '')}"
                    errors.append(error_dict)
            except (ValueError, TypeError) as e:
                msg = _format_constraint_message(constraint_obj, value, str(e))
                error_code = getattr(constraint_obj, "code", None) or type(constraint_obj).__name__
                errors.append({"field": field_name, "message": msg, "code": error_code})

        # NOTE: _recurse is intentionally omitted here to prevent O(N) useless tree walks on raw JSON

    if errors:
        raise ValidationError(errors)

    if drop_extra_keys:
        return {k: v for k, v in data.items() if k in allowed_keys}

    return data


def _prepare_stream_constraints(constraints: Iterable[Any]) -> list[MonkConstraint]:
    """Safely instantiates and filters constraints specifically for streams."""
    prepared: list[MonkConstraint] = []
    for constraint_item in constraints:
        if isinstance(constraint_item, type) and issubclass(constraint_item, MonkConstraint):
            try:
                constraint_item = constraint_item()
            except TypeError as e:
                raise TypeError(
                    f"Constraint '{constraint_item.__name__}' missing required arguments. Did you mean {constraint_item.__name__}(...)?"
                ) from e
        if isinstance(constraint_item, MonkConstraint):
            prepared.append(constraint_item)
    return prepared


def _validate_stream_item(item: Any, constraints: list[MonkConstraint], errors: list[ErrorDict]) -> None:
    """A simplified validation loop specifically for stream items."""
    item = settings.unwrap(item)
    if item is None:
        # Stream items are always considered required unless Nullable is present
        if not any(type(constraint_obj).__name__ == "Nullable" for constraint_obj in constraints):
            errors.append({"field": "", "message": "Stream items cannot be null.", "code": "NotNull"})
        return

    for constraint_obj in constraints:
        try:
            constraint_obj.validate(item)
        except ValidationError as e:
            for error_dict in e.errors:
                errors.append(error_dict)
        except (ValueError, TypeError) as e:
            error_code = getattr(constraint_obj, "code", None) or type(constraint_obj).__name__
            errors.append({"field": "", "message": str(e), "code": error_code})


def validate_stream(stream: Iterable[Any], *constraints: Any) -> Iterator[Any]:
    """Lazily validates an iterable/generator on the fly without consuming it entirely.

    Yields items one by one, raising a ValidationError instantly if an item fails.

    Args:
        stream (Iterable[Any]): The iterable or generator to validate.
        *constraints (Any): A variable number of constraint instances or classes to apply to each item.

    Yields:
        Any: The original item from the stream, assuming it passed validation.

    Raises:
        ValidationError: If any individual item fails validation.
    """
    prepared_constraints = _prepare_stream_constraints(constraints)

    for i, item in enumerate(stream):
        errors: list[ErrorDict] = []
        _validate_stream_item(item, prepared_constraints, errors)
        if errors:
            for error_dict in errors:
                error_dict["field"] = f"[{i}]{error_dict['field']}"
            raise ValidationError(errors)
        yield item


async def validate_async_stream(stream: AsyncIterable[Any], *constraints: Any) -> AsyncIterator[Any]:
    """Lazily validates an async iterable/generator on the fly without consuming it entirely.

    Yields items one by one, raising a ValidationError instantly if an item fails.

    Args:
        stream (AsyncIterable[Any]): The asynchronous iterable or generator to validate.
        *constraints (Any): A variable number of constraint instances or classes to apply to each item.

    Yields:
        Any: The original item from the async stream, assuming it passed validation.

    Raises:
        ValidationError: If any individual item fails validation.
    """
    prepared_constraints = _prepare_stream_constraints(constraints)

    i = 0
    async for item in stream:
        errors: list[ErrorDict] = []
        _validate_stream_item(item, prepared_constraints, errors)
        if errors:
            for error_dict in errors:
                error_dict["field"] = f"[{i}]{error_dict['field']}"
            raise ValidationError(errors)
        yield item
        i += 1


def _process_monk_validate_result(result: Any, errors: list[ErrorDict]) -> None:
    """Normalizes and processes the output of the __monk_validate__ hook."""
    if result is None:
        return

    items: Iterable[Any]
    # 1. Normalize the output: if it's a single string or single tuple, wrap it in a list
    if isinstance(result, str) or (isinstance(result, tuple) and len(result) > 0 and isinstance(result[0], str)):
        items = [result]
    elif isinstance(result, Iterable):
        items = result
    else:
        raise TypeError(f"Invalid yield/return from __monk_validate__: {result}. Expected a string or tuple.")

    # 2. Process the items
    for error_item in items:
        if isinstance(error_item, str):
            errors.append({"field": "__root__", "message": error_item, "code": "ModelRule"})
        elif isinstance(error_item, tuple):
            if not all(isinstance(item, str) for item in error_item):
                raise TypeError(
                    f"Invalid tuple items from __monk_validate__: {error_item}. All tuple items must be strings."
                )

            if len(error_item) == 1:
                errors.append({"field": "__root__", "message": error_item[0], "code": "ModelRule"})
            elif len(error_item) == 2:
                errors.append({"field": error_item[0], "message": error_item[1], "code": "ModelRule"})
            elif len(error_item) == 3:
                errors.append({"field": error_item[0], "message": error_item[1], "code": error_item[2]})
            else:
                raise TypeError(
                    f"Invalid tuple length from __monk_validate__: {error_item}. Expected 1, 2, or 3 items."
                )
        else:
            raise TypeError(
                f"Invalid item yielded/returned from __monk_validate__: {error_item}. Expected a string or tuple."
            )


def validate(instance: T, *, context: Mapping[str, Any] | None = None) -> T:
    """Validates a Monk dataclass instance.

    Executes all field-level constraints. If all field-level constraints pass, it then executes
    the model-level `__monk_validate__` hook if present. Returns the instance so it can be used inline or reassigned.

    Args:
        instance (T): The instantiated Monk dataclass to validate.
        context (Mapping[str, Any] | None, optional): Read-only mapping used to resolve
            ``Ctx(key)`` markers inside constraints. Also forwarded to
            ``__monk_validate__`` when its signature accepts a second positional argument.
            Defaults to None.

    Returns:
        T: The validated dataclass instance, which is now fully unlocked for attribute access.

    Raises:
        TypeError: If the provided instance is not a valid Monk dataclass, or if an async cross-field hook is used.
        ValidationError: If the instance fails validation.
        MissingContextError: If a constraint references ``Ctx(...)`` but no context was provided.
    """
    try:
        rules = _obj_ga(instance, "__monk_rules__")
        fields = _obj_ga(instance, "__monk_fields__")
    except AttributeError:
        raise TypeError(f"Object of type {type(instance).__name__} is not a valid Monk dataclass.") from None

    errors: list[ErrorDict] = []
    unwrap = settings.unwrap
    default_allow_none = settings.default_allow_none
    primitives = _PRIMITIVE_TYPES

    resolver: Callable[[str], Any] | None = None
    ctx_resolver: Callable[[str], Any] | None = context.__getitem__ if context is not None else None

    for field_name in fields:
        raw_value = _obj_ga(instance, field_name)
        rule_tuple = rules.get(field_name)

        if rule_tuple:
            constraints, is_outer_nullable, is_inner_nullable, is_not_null, not_null_constraint = rule_tuple

            if raw_value is None:
                if not is_outer_nullable and (is_not_null or not default_allow_none):
                    msg = getattr(not_null_constraint, "message", None) or "Field is required and cannot be null."
                    code = getattr(not_null_constraint, "code", None) or "NotNull"
                    errors.append({"field": field_name, "message": msg, "code": code})
                continue

            value = unwrap(raw_value)
            if value is None:
                if not is_inner_nullable and (is_not_null or not default_allow_none):
                    msg = getattr(not_null_constraint, "message", None) or "Field is required and cannot be null."
                    code = getattr(not_null_constraint, "code", None) or "NotNull"
                    errors.append({"field": field_name, "message": msg, "code": code})
                continue

            for constraint_obj, blueprint in constraints:
                if blueprint is not None:
                    if resolver is None:
                        resolver = _make_resolver(instance)
                    try:
                        constraint_to_validate = _execute_blueprint(constraint_obj, blueprint, resolver, ctx_resolver)
                    except ValidationError as e:
                        for error_dict in e.errors:
                            error_dict["field"] = f"{field_name}{error_dict.get('field', '')}"
                            errors.append(error_dict)
                        continue
                    # Cloned constraints have ephemeral ids — bypass cache to avoid leak.
                    fn = getattr(constraint_to_validate, "_validate_inner", None) or constraint_to_validate.validate
                else:
                    fn = getattr(constraint_obj, "_validate_inner", None) or constraint_obj.validate
                try:
                    fn(value)
                except ValidationError as e:
                    for error_dict in e.errors:
                        error_dict["field"] = f"{field_name}{error_dict.get('field', '')}"
                        errors.append(error_dict)
                except (ValueError, TypeError) as e:
                    msg = _format_constraint_message(constraint_obj, value, str(e))
                    error_code = getattr(constraint_obj, "code", None) or type(constraint_obj).__name__
                    errors.append({"field": field_name, "message": msg, "code": error_code})

            if type(value) not in primitives:
                _recurse(value, field_name, errors, context)
        else:
            value = unwrap(raw_value)
            if type(value) not in primitives:
                _recurse(value, field_name, errors, context)

    if not errors and _obj_ga(type(instance), "__monk_has_validate_hook__"):
        hook = getattr(instance, "__monk_validate__", None)
        if hook is not None:
            if inspect.iscoroutinefunction(hook) or inspect.isasyncgenfunction(hook):
                raise TypeError("iron-monk is strictly synchronous. Async __monk_validate__ hooks are not supported.")

            # Field-level validation passed; uncloak so the hook can read sibling
            # fields without tripping the guard. Recloak if the hook fails or the
            # final aggregated result still has errors.
            _obj_sa(instance, "__monk_safe__", True)
            try:
                if _obj_ga(type(instance), "__monk_validate_wants_ctx__"):
                    result = hook(context)
                else:
                    result = hook()
                _process_monk_validate_result(result, errors)
            except BaseException:
                _obj_sa(instance, "__monk_safe__", False)
                raise
            if errors:
                _obj_sa(instance, "__monk_safe__", False)

    if errors:
        raise ValidationError(errors)

    # Uncloak the instance (idempotent if the hook already did so).
    _obj_sa(instance, "__monk_safe__", True)

    return instance
