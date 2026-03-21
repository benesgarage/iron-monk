import dataclasses
import functools
from typing import TypeVar, Any, cast, Iterable, get_origin, get_args, get_type_hints
from .exceptions import ValidationError
from .types import ErrorDict
from .config import settings
from .protocols import MonkConstraint

T = TypeVar("T")


def _extract_monk_metadata(hints: dict[str, Any]) -> dict[str, list[MonkConstraint]]:
    """Extracts validation rules from type hints."""
    rules: dict[str, list[MonkConstraint]] = {}

    for name, hint in hints.items():
        # Look for our specific MonkConstraint in Annotated metadata
        metadata = getattr(hint, "__metadata__", [])

        # Support framework wrappers (like SQLAlchemy's Mapped[Annotated[...]])
        if not metadata:
            args = get_args(hint)
            origin = get_origin(hint)
            # Only unwrap if it's not a standard collection (collections use Each constraint)
            if args and origin not in (list, set, frozenset, tuple, dict):
                metadata = getattr(args[0], "__metadata__", [])

        field_rules = []
        for m in metadata:
            # Auto-instantiate classes that implement the protocol but were passed as a type
            if isinstance(m, type) and issubclass(m, MonkConstraint):
                try:
                    field_rules.append(m())
                except TypeError as e:
                    raise TypeError(
                        f"Constraint '{m.__name__}' missing required arguments. Did you mean {m.__name__}(...)?"
                    ) from e
            elif isinstance(m, MonkConstraint):
                field_rules.append(m)

        if field_rules:
            rules[name] = field_rules

    return rules


def _is_nullable(c: Any) -> bool:
    """Duck-type check to avoid circular imports."""
    return getattr(c, "__name__", type(c).__name__) == "Nullable"


def _is_not_null(c: Any) -> bool:
    """Duck-type check to avoid circular imports."""
    return getattr(c, "__name__", type(c).__name__) == "NotNull"


def _validate_field_and_recurse(
    field_name: str,
    value: Any,
    constraints: list[Any],
    errors: list[ErrorDict],
) -> None:
    """Core validation loop shared by both dataclasses and function arguments."""
    if value is None:
        if constraints:
            is_explicitly_nullable = any(_is_nullable(c) for c in constraints)
            is_explicitly_not_null = any(_is_not_null(c) for c in constraints)

            allows_none = (
                True if is_explicitly_nullable else (False if is_explicitly_not_null else settings.default_allow_none)
            )

            if not allows_none:
                not_null_c = next((c for c in constraints if _is_not_null(c)), None)
                msg = getattr(not_null_c, "message", None) or "Field is required and cannot be null."
                code = getattr(not_null_c, "code", None) or "NotNull"
                errors.append({"field": field_name, "message": msg, "code": code})
        return

    for c in constraints:
        if _is_nullable(c) or _is_not_null(c):
            continue
        try:
            c.validate(value)
        except ValidationError as e:
            for err in e.errors:
                err["field"] = f"{field_name}{err.get('field', '')}"
                errors.append(err)
        except (ValueError, TypeError) as e:
            error_code = getattr(c, "code", None) or type(c).__name__
            errors.append({"field": field_name, "message": str(e), "code": error_code})

    # Helper function to recursively validate nested Monk objects and bubble up errors
    def _recurse(val: Any, prefix: str) -> None:
        if hasattr(val, "__monk_rules__"):
            try:
                validate(val)
            except ValidationError as e:
                for err in e.errors:
                    err["field"] = f"{prefix}.{err['field']}"
                    errors.append(err)
        elif isinstance(val, (list, tuple, set)):
            for i, item in enumerate(val):
                _recurse(item, f"{prefix}[{i}]")
        elif isinstance(val, dict):
            for k, v in val.items():
                _recurse(v, f"{prefix}[{repr(k)}]")

    _recurse(value, field_name)


def validate_arguments(arguments: dict[str, Any], rules: dict[str, list[Any]]) -> None:
    """Validates a dictionary of function arguments against extracted constraints."""
    errors: list[ErrorDict] = []
    for arg_name, value in arguments.items():
        constraints = rules.get(arg_name, [])
        _validate_field_and_recurse(arg_name, value, constraints, errors)

    if errors:
        raise ValidationError(errors)


def validate_return(value: Any, constraints: list[Any]) -> None:
    """Validates a function's return value against extracted constraints."""
    errors: list[ErrorDict] = []
    _validate_field_and_recurse("return", value, constraints, errors)

    if errors:
        raise ValidationError(errors)


@functools.lru_cache(maxsize=None)
def _get_schema_rules(schema: type) -> dict[str, list[MonkConstraint]]:
    """Caches the extracted rules for a given TypedDict schema to maximize performance."""
    hints = get_type_hints(schema, include_extras=True)
    return _extract_monk_metadata(hints)


def validate_dict(data: dict[str, Any], schema: type) -> dict[str, Any]:
    """Validates a raw dictionary against a TypedDict schema without instantiating an object."""
    rules = _get_schema_rules(schema)
    errors: list[ErrorDict] = []

    # We iterate over the SCHEMA rules to catch missing required fields
    for field_name, constraints in rules.items():
        value = data.get(field_name)
        _validate_field_and_recurse(field_name, value, constraints, errors)

    if errors:
        raise ValidationError(errors)

    return data


def validate(instance: T) -> T:
    """
    Validates a Monk dataclass instance.
    Returns the instance so it can be used inline or reassigned.
    """
    if not hasattr(instance, "__monk_rules__"):
        raise TypeError(f"Object of type {type(instance).__name__} is not a valid Monk dataclass.")

    errors: list[ErrorDict] = []
    rules = getattr(instance, "__monk_rules__", {})

    for field_info in dataclasses.fields(cast(Any, instance)):
        field_name = field_info.name
        value = object.__getattribute__(instance, field_name)
        constraints = rules.get(field_name, [])

        _validate_field_and_recurse(field_name, value, constraints, errors)

    # Run cross-field validation ONLY if all field-level rules passed
    if not errors and hasattr(instance, "__monk_validate__"):
        result = instance.__monk_validate__()

        if result is not None:
            items: Iterable[Any]
            # 1. Normalize the output: if it's a single string or single tuple, wrap it in a list
            if isinstance(result, str) or (
                isinstance(result, tuple) and len(result) > 0 and isinstance(result[0], str)
            ):
                items = [result]
            elif isinstance(result, Iterable):
                items = result
            else:
                raise TypeError(f"Invalid yield/return from __monk_validate__: {result}. Expected a string or tuple.")

            # 2. Process the items
            for err in items:
                if isinstance(err, str):
                    errors.append({"field": "__root__", "message": err, "code": "ModelRule"})
                elif isinstance(err, tuple):
                    if not all(isinstance(item, str) for item in err):
                        raise TypeError(
                            f"Invalid tuple items from __monk_validate__: {err}. All tuple items must be strings."
                        )

                    if len(err) == 1:
                        errors.append({"field": "__root__", "message": err[0], "code": "ModelRule"})
                    elif len(err) == 2:
                        errors.append({"field": err[0], "message": err[1], "code": "ModelRule"})
                    elif len(err) == 3:
                        errors.append({"field": err[0], "message": err[1], "code": err[2]})
                    else:
                        raise TypeError(
                            f"Invalid tuple length from __monk_validate__: {err}. Expected 1, 2, or 3 items."
                        )
                else:
                    raise TypeError(
                        f"Invalid item yielded/returned from __monk_validate__: {err}. Expected a string or tuple."
                    )

    if errors:
        raise ValidationError(errors)

    # Uncloak the instance
    object.__setattr__(instance, "__monk_safe__", True)

    return instance
