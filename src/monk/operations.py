import dataclasses
from typing import TypeVar, Any, cast, Iterable
from .exceptions import ValidationError
from .types import ErrorDict

T = TypeVar("T")


def validate(instance: T) -> T:
    """
    Validates a Monk dataclass instance.
    Returns the instance so it can be used inline or reassigned.
    """
    if not hasattr(instance, "__monk_rules__"):
        raise TypeError(f"Object of type {type(instance).__name__} is not a valid Monk dataclass.")

    errors: list[ErrorDict] = []

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
                c.validate(value)
            except ValidationError as e:
                for err in e.errors:
                    err["field"] = f"{field}{err.get('field', '')}"
                    errors.append(err)
            except (ValueError, TypeError) as e:
                errors.append({"field": field, "message": str(e), "constraint": type(c).__name__})

    # Recursively validate nested Monk objects
    for field_info in dataclasses.fields(cast(Any, instance)):
        value = object.__getattribute__(instance, field_info.name)

        _recurse(value, field_info.name)

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
                    errors.append({"field": "__root__", "message": err, "constraint": "ModelRule"})
                elif isinstance(err, tuple):
                    if not all(isinstance(item, str) for item in err):
                        raise TypeError(
                            f"Invalid tuple items from __monk_validate__: {err}. All tuple items must be strings."
                        )

                    if len(err) == 1:
                        errors.append({"field": "__root__", "message": err[0], "constraint": "ModelRule"})
                    elif len(err) == 2:
                        errors.append({"field": err[0], "message": err[1], "constraint": "ModelRule"})
                    elif len(err) == 3:
                        errors.append({"field": err[0], "message": err[1], "constraint": err[2]})
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
