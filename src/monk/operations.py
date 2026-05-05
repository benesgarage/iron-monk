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
    get_origin,
    get_args,
    get_type_hints,
    Union,
    cast,
)
from .exceptions import ValidationError
from .types import ErrorDict
from .config import settings
from .protocols import MonkConstraint

T = TypeVar("T")

_PRIMITIVE_TYPES = frozenset((str, int, float, bool, type(None)))

_UNION_TYPES: tuple[Any, ...] = (Union, types.UnionType)


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
            if type(value).__name__ == "Ref":
                refs[field_name] = value
                has_refs = True
        except AttributeError:
            pass

    # Check known nested constraint fields (like DictOf, CSV, AnyOf, Not, etc.)
    nested: dict[str, Any] = {}
    for nested_attr in ("constraints", "_key_constraints", "_value_constraints", "_prepared", "constraint"):
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
) -> Any:
    """
    Clones a constraint and maps Ref values using the compiled blueprint.
    get_val is the method which fetches the Ref values
    """
    cloned_constraint = type(constraint).__new__(type(constraint))  # type: ignore[call-overload]

    for attr_name in blueprint.clone_attrs:
        object.__setattr__(cloned_constraint, attr_name, getattr(constraint, attr_name))

    for attr_name, ref_obj in blueprint.refs.items():
        resolved_val = settings.unwrap(get_val(ref_obj.field_name))
        object.__setattr__(cloned_constraint, attr_name, resolved_val)

    for nested_attr, nested_blueprint in blueprint.nested.items():
        if nested_attr == "union_branches":
            val = getattr(cloned_constraint, nested_attr)
            new_val = []
            for (branch_type, branch_constraints), branch_blueprints in zip(val, nested_blueprint):
                new_constraint = []
                for (inner_constraint, _), inner_blueprint in zip(branch_constraints, branch_blueprints):
                    if inner_blueprint is not None:
                        new_constraint.append((_execute_blueprint(inner_constraint, inner_blueprint, get_val), None))
                    else:
                        new_constraint.append((inner_constraint, None))
                new_val.append((branch_type, new_constraint))
            object.__setattr__(cloned_constraint, nested_attr, new_val)
            continue

        val = getattr(cloned_constraint, nested_attr)
        if isinstance(val, tuple):
            new_val_tuple = tuple(
                _execute_blueprint(inner_constraint, inner_blueprint, get_val) if inner_blueprint else inner_constraint
                for inner_constraint, inner_blueprint in zip(val, nested_blueprint)
            )
            object.__setattr__(cloned_constraint, nested_attr, new_val_tuple)
        elif isinstance(val, list):
            new_val_list = [
                _execute_blueprint(inner_constraint, inner_blueprint, get_val) if inner_blueprint else inner_constraint
                for inner_constraint, inner_blueprint in zip(val, nested_blueprint)
            ]
            object.__setattr__(cloned_constraint, nested_attr, new_val_list)
        else:
            new_val_single = _execute_blueprint(val, nested_blueprint, get_val)
            object.__setattr__(cloned_constraint, nested_attr, new_val_single)

    return cloned_constraint


class _UnionRouter(MonkConstraint):
    """An internal constraint used to route and evaluate Union branches."""

    def __init__(self, union_branches: list[tuple[Any, list[tuple[MonkConstraint, _RefBlueprint | None]]]]) -> None:
        self.union_branches = union_branches
        self.code = "Union"

    def validate(self, value: Any) -> None:
        errors: list[Exception] = []
        for branch_type, branch in self.union_branches:
            origin = get_origin(branch_type) or branch_type
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
                try:
                    constraint_obj.validate(value)
                except ValidationError as e:
                    errors.append(e)
                    branch_passed = False
                    break
                except (ValueError, TypeError) as e:
                    error_code = getattr(constraint_obj, "code", None) or type(constraint_obj).__name__
                    errors.append(ValidationError([{"field": "", "message": str(e), "code": error_code}]))
                    branch_passed = False
                    break
            if branch_passed:
                return

        if len(errors) == 1:
            raise errors[0]

        raise ValueError("Value did not match any of the allowed union branches. Must satisfy at least one.")


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


def _extract_monk_metadata(
    hints: dict[str, Any],
) -> dict[str, tuple[list[tuple[MonkConstraint, _RefBlueprint | None]], bool, bool, bool, Any]]:
    """Extracts validation rules from type hints into highly optimized structures."""
    rules: dict[str, tuple[list[tuple[MonkConstraint, _RefBlueprint | None]], bool, bool, bool, Any]] = {}
    type_meta_map = getattr(settings, "type_metadata", {})

    for name, hint in hints.items():
        metadata = getattr(hint, "__metadata__", [])
        extra_meta = type_meta_map.get(get_origin(hint) or hint, [])

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
                    arg_metadata = getattr(arg, "__metadata__", [])

                    if not arg_metadata:
                        inner_args = get_args(arg)
                        inner_origin = get_origin(arg)
                        if (
                            inner_args
                            and inner_origin not in (list, set, frozenset, tuple, dict)
                            and inner_origin not in _UNION_TYPES
                        ):
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


def _recurse(val: Any, prefix: str, errors: list[ErrorDict]) -> None:
    """Recursively validates nested Monk objects and bubbles up errors."""
    val = settings.unwrap(val)
    # getattr(..., None) is faster than hasattr + getattr
    if getattr(val, "__monk_rules__", None) is not None:
        try:
            validate(val)
        except ValidationError as e:
            for err in e.errors:
                err["field"] = f"{prefix}.{err['field']}"
                errors.append(err)
        return

    # Exact type checking is significantly faster than isinstance abstract base class checks
    val_type = type(val)
    if val_type is list or val_type is tuple:
        for i, item in enumerate(val):
            if type(item) not in _PRIMITIVE_TYPES:
                _recurse(item, f"{prefix}[{i}]", errors)
    elif val_type is dict:
        for key, value in val.items():
            if type(value) not in _PRIMITIVE_TYPES:
                _recurse(value, f"{prefix}[{repr(key)}]", errors)
    elif val_type is set or val_type is frozenset:  # Cannot be indexed
        for item in val:
            if type(item) not in _PRIMITIVE_TYPES:
                _recurse(item, prefix, errors)


def validate_arguments(
    arguments: dict[str, Any],
    rules: dict[str, tuple[list[tuple[MonkConstraint, _RefBlueprint | None]], bool, bool, bool, Any]],
) -> None:
    """Validates a dictionary of function arguments against extracted constraints."""
    errors: list[ErrorDict] = []
    for arg_name, raw_value in arguments.items():
        rule_tuple = rules.get(arg_name)
        if rule_tuple:
            constraints, is_outer_nullable, is_inner_nullable, is_not_null, not_null_constraint = rule_tuple

            if raw_value is None:
                if not is_outer_nullable and (is_not_null or not settings.default_allow_none):
                    msg = getattr(not_null_constraint, "message", None) or "Field is required and cannot be null."
                    code = getattr(not_null_constraint, "code", None) or "NotNull"
                    errors.append({"field": arg_name, "message": msg, "code": code})
                continue

            value = settings.unwrap(raw_value)
            if value is None:
                if not is_inner_nullable and (is_not_null or not settings.default_allow_none):
                    msg = getattr(not_null_constraint, "message", None) or "Field is required and cannot be null."
                    code = getattr(not_null_constraint, "code", None) or "NotNull"
                    errors.append({"field": arg_name, "message": msg, "code": code})
                continue

            for constraint_obj, blueprint in constraints:
                if blueprint is not None:
                    constraint_to_validate = _execute_blueprint(constraint_obj, blueprint, arguments.get)
                    try:
                        constraint_to_validate.validate(value)
                    except ValidationError as e:
                        for error_dict in e.errors:
                            error_dict["field"] = f"{arg_name}{error_dict.get('field', '')}"
                            errors.append(error_dict)
                    except (ValueError, TypeError) as e:
                        error_code = getattr(constraint_obj, "code", None) or type(constraint_obj).__name__
                        errors.append({"field": arg_name, "message": str(e), "code": error_code})
                else:
                    try:
                        constraint_obj.validate(value)
                    except ValidationError as e:
                        for error_dict in e.errors:
                            error_dict["field"] = f"{arg_name}{error_dict.get('field', '')}"
                            errors.append(error_dict)
                    except (ValueError, TypeError) as e:
                        error_code = getattr(constraint_obj, "code", None) or type(constraint_obj).__name__
                        errors.append({"field": arg_name, "message": str(e), "code": error_code})

            if type(value) not in _PRIMITIVE_TYPES:
                _recurse(value, arg_name, errors)
        else:
            value = settings.unwrap(raw_value)
            if type(value) not in _PRIMITIVE_TYPES:
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
                try:
                    constraint_obj.validate(value)
                except ValidationError as e:
                    for error_dict in e.errors:
                        error_dict["field"] = f"return{error_dict.get('field', '')}"
                        errors.append(error_dict)
                except (ValueError, TypeError) as e:
                    error_code = getattr(constraint_obj, "code", None) or type(constraint_obj).__name__
                    errors.append({"field": "return", "message": str(e), "code": error_code})

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
    data: dict[str, Any], schema: type, *, partial: bool = False, drop_extra_keys: bool = False
) -> dict[str, Any]:
    """Validates a raw dictionary against a TypedDict or Dataclass schema without instantiating an object.

    Args:
        data (dict[str, Any]): The raw dictionary payload to validate.
        schema (type): The TypedDict or Dataclass schema containing the validation rules.
        partial (bool, optional): If True, ignores keys that are missing from the payload (useful for PATCH requests). Defaults to False.
        drop_extra_keys (bool, optional): If True, strips any keys not explicitly defined in the schema. Defaults to False.

    Returns:
        dict[str, Any]: The validated (and optionally sanitized) dictionary.

    Raises:
        ValidationError: If the dictionary fails any validation constraints or contains unrecognized keys (when drop_extra_keys is False).
    """
    allowed_keys, rules = _get_schema_rules(schema)
    errors: list[ErrorDict] = []

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
            if not is_outer_nullable and (is_not_null or not settings.default_allow_none):
                msg = getattr(not_null_constraint, "message", None) or "Field is required and cannot be null."
                code = getattr(not_null_constraint, "code", None) or "NotNull"
                errors.append({"field": field_name, "message": msg, "code": code})
            continue

        value = settings.unwrap(raw_value)
        if value is None:
            if not is_inner_nullable and (is_not_null or not settings.default_allow_none):
                msg = getattr(not_null_constraint, "message", None) or "Field is required and cannot be null."
                code = getattr(not_null_constraint, "code", None) or "NotNull"
                errors.append({"field": field_name, "message": msg, "code": code})
            continue

        for constraint_obj, blueprint in constraints:
            if blueprint is not None:
                constraint_to_validate = _execute_blueprint(constraint_obj, blueprint, data.get)
                try:
                    constraint_to_validate.validate(value)
                except ValidationError as e:
                    for error_dict in e.errors:
                        error_dict["field"] = f"{field_name}{error_dict.get('field', '')}"
                        errors.append(error_dict)
                except (ValueError, TypeError) as e:
                    error_code = getattr(constraint_obj, "code", None) or type(constraint_obj).__name__
                    errors.append({"field": field_name, "message": str(e), "code": error_code})
            else:
                try:
                    constraint_obj.validate(value)
                except ValidationError as e:
                    for error_dict in e.errors:
                        error_dict["field"] = f"{field_name}{error_dict.get('field', '')}"
                        errors.append(error_dict)
                except (ValueError, TypeError) as e:
                    error_code = getattr(constraint_obj, "code", None) or type(constraint_obj).__name__
                    errors.append({"field": field_name, "message": str(e), "code": error_code})

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


def validate(instance: T) -> T:
    """Validates a Monk dataclass instance.

    Executes all field-level constraints. If all field-level constraints pass, it then executes
    the model-level `__monk_validate__` hook if present. Returns the instance so it can be used inline or reassigned.

    Args:
        instance (T): The instantiated Monk dataclass to validate.

    Returns:
        T: The validated dataclass instance, which is now fully unlocked for attribute access.

    Raises:
        TypeError: If the provided instance is not a valid Monk dataclass, or if an async cross-field hook is used.
        ValidationError: If the instance fails validation.
    """
    if getattr(instance, "__monk_rules__", None) is None:
        raise TypeError(f"Object of type {type(instance).__name__} is not a valid Monk dataclass.")

    errors: list[ErrorDict] = []
    rules = object.__getattribute__(instance, "__monk_rules__")
    fields = object.__getattribute__(instance, "__monk_fields__")

    for field_name in fields:
        raw_value = object.__getattribute__(instance, field_name)
        rule_tuple = rules.get(field_name)

        if rule_tuple:
            constraints, is_outer_nullable, is_inner_nullable, is_not_null, not_null_constraint = rule_tuple

            if raw_value is None:
                if not is_outer_nullable and (is_not_null or not settings.default_allow_none):
                    msg = getattr(not_null_constraint, "message", None) or "Field is required and cannot be null."
                    code = getattr(not_null_constraint, "code", None) or "NotNull"
                    errors.append({"field": field_name, "message": msg, "code": code})
                continue

            value = settings.unwrap(raw_value)
            if value is None:
                if not is_inner_nullable and (is_not_null or not settings.default_allow_none):
                    msg = getattr(not_null_constraint, "message", None) or "Field is required and cannot be null."
                    code = getattr(not_null_constraint, "code", None) or "NotNull"
                    errors.append({"field": field_name, "message": msg, "code": code})
                continue

            _resolver: Callable[[str], Any] | None = None
            if any(blueprint is not None for _, blueprint in constraints):

                def _instance_resolver(target_field_name: str) -> Any:
                    try:
                        return object.__getattribute__(instance, target_field_name)
                    except AttributeError:
                        return None

                _resolver = _instance_resolver

            for constraint_obj, blueprint in constraints:
                if blueprint is not None:
                    constraint_to_validate = _execute_blueprint(
                        constraint_obj, blueprint, cast(Callable[[str], Any], _resolver)
                    )
                    try:
                        constraint_to_validate.validate(value)
                    except ValidationError as e:
                        for error_dict in e.errors:
                            error_dict["field"] = f"{field_name}{error_dict.get('field', '')}"
                            errors.append(error_dict)
                    except (ValueError, TypeError) as e:
                        error_code = getattr(constraint_obj, "code", None) or type(constraint_obj).__name__
                        errors.append({"field": field_name, "message": str(e), "code": error_code})
                else:
                    try:
                        constraint_obj.validate(value)
                    except ValidationError as e:
                        for error_dict in e.errors:
                            error_dict["field"] = f"{field_name}{error_dict.get('field', '')}"
                            errors.append(error_dict)
                    except (ValueError, TypeError) as e:
                        error_code = getattr(constraint_obj, "code", None) or type(constraint_obj).__name__
                        errors.append({"field": field_name, "message": str(e), "code": error_code})

            if type(value) not in _PRIMITIVE_TYPES:
                _recurse(value, field_name, errors)
        else:
            value = settings.unwrap(raw_value)
            if type(value) not in _PRIMITIVE_TYPES:
                _recurse(value, field_name, errors)

    if not errors:
        hook = getattr(instance, "__monk_validate__", None)
        if hook is not None:
            if inspect.iscoroutinefunction(hook) or inspect.isasyncgenfunction(hook):
                raise TypeError("iron-monk is strictly synchronous. Async __monk_validate__ hooks are not supported.")

            result = hook()
            _process_monk_validate_result(result, errors)

    if errors:
        raise ValidationError(errors)

    # Uncloak the instance
    object.__setattr__(instance, "__monk_safe__", True)

    return instance
