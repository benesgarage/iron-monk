import dataclasses
from typing import TypeVar, Any, cast
from .exceptions import ValidationError

T = TypeVar("T")


def validate(instance: T) -> T:
    """
    Validates a Monk dataclass instance.
    Returns the instance so it can be used inline or reassigned.
    """
    if not hasattr(instance, "__monk_rules__"):
        raise TypeError(f"Object of type {type(instance).__name__} is not a valid Monk dataclass.")

    errors: list[dict[str, Any]] = []

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

    rules = getattr(instance, "__monk_rules__", {})
    for field, constraints in rules.items():
        value = object.__getattribute__(instance, field)
        for c in constraints:
            try:
                c.validate(field, value)
            except ValidationError as e:
                errors.extend(e.errors)
            except (ValueError, TypeError) as e:
                errors.append({"field": field, "message": str(e), "constraint": type(c).__name__})

    # Recursively validate nested Monk objects
    for field_info in dataclasses.fields(cast(Any, instance)):
        value = object.__getattribute__(instance, field_info.name)

        _recurse(value, field_info.name)

    if errors:
        raise ValidationError(errors)

    # Uncloak the instance
    object.__setattr__(instance, "__monk_safe__", True)

    return instance
