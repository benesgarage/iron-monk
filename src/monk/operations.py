import functools
import inspect
from typing import (
    TypeVar,
    Any,
    Iterable,
    AsyncIterable,
    AsyncIterator,
    Iterator,
    get_origin,
    get_args,
    get_type_hints,
)
from .exceptions import ValidationError
from .types import ErrorDict
from .config import settings
from .protocols import MonkConstraint

T = TypeVar("T")

_PRIMITIVE_TYPES = frozenset((str, int, float, bool, type(None)))


def _prepare_constraints(constraints: Iterable[Any]) -> tuple[list[MonkConstraint], bool, bool, Any]:
    """Takes raw constraints and compiles them into a highly optimized validation tuple."""
    actual_constraints: list[MonkConstraint] = []
    is_nullable = False
    is_not_null = False
    not_null_c = None

    for m in constraints:
        if isinstance(m, type) and issubclass(m, MonkConstraint):
            try:
                m = m()
            except TypeError as e:
                raise TypeError(
                    f"Constraint '{m.__name__}' missing required arguments. Did you mean {m.__name__}(...)?"
                ) from e

        if not isinstance(m, MonkConstraint):
            continue

        c_name = type(m).__name__
        if c_name == "Nullable":
            is_nullable = True
        elif c_name == "NotNull":
            is_not_null = True
            not_null_c = m
        else:
            actual_constraints.append(m)

    return actual_constraints, is_nullable, is_not_null, not_null_c


def _extract_monk_metadata(hints: dict[str, Any]) -> dict[str, tuple[list[MonkConstraint], bool, bool, Any]]:
    """Extracts validation rules from type hints into highly optimized structures."""
    rules: dict[str, tuple[list[MonkConstraint], bool, bool, Any]] = {}

    for name, hint in hints.items():
        metadata = getattr(hint, "__metadata__", [])

        if not metadata:
            args = get_args(hint)
            origin = get_origin(hint)
            if args and origin not in (list, set, frozenset, tuple, dict):
                metadata = getattr(args[0], "__metadata__", [])

        if metadata:
            compiled_rules = _prepare_constraints(metadata)
            # Only store it if there are actual constraints or nullability overrides
            if compiled_rules[0] or compiled_rules[1] or compiled_rules[2]:
                rules[name] = compiled_rules

    return rules


def _recurse(val: Any, prefix: str, errors: list[ErrorDict]) -> None:
    """Recursively validates nested Monk objects and bubbles up errors."""
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
        for k, v in val.items():
            if type(v) not in _PRIMITIVE_TYPES:
                _recurse(v, f"{prefix}[{repr(k)}]", errors)
    elif val_type is set or val_type is frozenset:  # Cannot be indexed
        for item in val:
            if type(item) not in _PRIMITIVE_TYPES:
                _recurse(item, prefix, errors)


def validate_arguments(
    arguments: dict[str, Any], rules: dict[str, tuple[list[MonkConstraint], bool, bool, Any]]
) -> None:
    """Validates a dictionary of function arguments against extracted constraints."""
    errors: list[ErrorDict] = []
    for arg_name, value in arguments.items():
        rule_tuple = rules.get(arg_name)
        if rule_tuple:
            constraints, is_nullable, is_not_null, not_null_c = rule_tuple

            if value is None:
                if not is_nullable and (is_not_null or not settings.default_allow_none):
                    msg = getattr(not_null_c, "message", None) or "Field is required and cannot be null."
                    code = getattr(not_null_c, "code", None) or "NotNull"
                    errors.append({"field": arg_name, "message": msg, "code": code})
                continue

            for c in constraints:
                try:
                    c.validate(value)
                except ValidationError as e:
                    for err in e.errors:
                        err["field"] = f"{arg_name}{err.get('field', '')}"
                        errors.append(err)
                except (ValueError, TypeError) as e:
                    error_code = getattr(c, "code", None) or type(c).__name__
                    errors.append({"field": arg_name, "message": str(e), "code": error_code})

            if type(value) not in _PRIMITIVE_TYPES:
                _recurse(value, arg_name, errors)
        elif type(value) not in _PRIMITIVE_TYPES:
            _recurse(value, arg_name, errors)

    if errors:
        raise ValidationError(errors)


def validate_return(value: Any, rule_tuple: tuple[list[MonkConstraint], bool, bool, Any]) -> None:
    """Validates a function's return value against extracted constraints."""
    errors: list[ErrorDict] = []
    constraints, is_nullable, is_not_null, not_null_c = rule_tuple

    if value is None:
        if not is_nullable and (is_not_null or not settings.default_allow_none):
            msg = getattr(not_null_c, "message", None) or "Field is required and cannot be null."
            code = getattr(not_null_c, "code", None) or "NotNull"
            errors.append({"field": "return", "message": msg, "code": code})
    else:
        for c in constraints:
            try:
                c.validate(value)
            except ValidationError as e:
                for err in e.errors:
                    err["field"] = f"return{err.get('field', '')}"
                    errors.append(err)
            except (ValueError, TypeError) as e:
                error_code = getattr(c, "code", None) or type(c).__name__
                errors.append({"field": "return", "message": str(e), "code": error_code})

        if type(value) not in _PRIMITIVE_TYPES:
            _recurse(value, "return", errors)

    if errors:
        raise ValidationError(errors)


@functools.lru_cache(maxsize=None)
def _get_schema_rules(schema: type) -> tuple[set[str], dict[str, tuple[list[MonkConstraint], bool, bool, Any]]]:
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

        value = data.get(field_name)
        constraints, is_nullable, is_not_null, not_null_c = rule_tuple

        if value is None:
            if not is_nullable and (is_not_null or not settings.default_allow_none):
                msg = getattr(not_null_c, "message", None) or "Field is required and cannot be null."
                code = getattr(not_null_c, "code", None) or "NotNull"
                errors.append({"field": field_name, "message": msg, "code": code})
            continue

        for c in constraints:
            try:
                c.validate(value)
            except ValidationError as e:
                for err in e.errors:
                    err["field"] = f"{field_name}{err.get('field', '')}"
                    errors.append(err)
            except (ValueError, TypeError) as e:
                error_code = getattr(c, "code", None) or type(c).__name__
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
    for c in constraints:
        if isinstance(c, type) and issubclass(c, MonkConstraint):
            try:
                c = c()
            except TypeError as e:
                raise TypeError(
                    f"Constraint '{c.__name__}' missing required arguments. Did you mean {c.__name__}(...)?"
                ) from e
        if isinstance(c, MonkConstraint):
            prepared.append(c)
    return prepared


def _validate_stream_item(item: Any, constraints: list[MonkConstraint], errors: list[ErrorDict]) -> None:
    """A simplified validation loop specifically for stream items."""
    if item is None:
        # Stream items are always considered required unless Nullable is present
        if not any(type(c).__name__ == "Nullable" for c in constraints):
            errors.append({"field": "", "message": "Stream items cannot be null.", "code": "NotNull"})
        return

    for c in constraints:
        try:
            c.validate(item)
        except (ValueError, TypeError) as e:
            error_code = getattr(c, "code", None) or type(c).__name__
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
            for err in errors:
                err["field"] = f"[{i}]{err['field']}"
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
            for err in errors:
                err["field"] = f"[{i}]{err['field']}"
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
    for err in items:
        if isinstance(err, str):
            errors.append({"field": "__root__", "message": err, "code": "ModelRule"})
        elif isinstance(err, tuple):
            if not all(isinstance(item, str) for item in err):
                raise TypeError(f"Invalid tuple items from __monk_validate__: {err}. All tuple items must be strings.")

            if len(err) == 1:
                errors.append({"field": "__root__", "message": err[0], "code": "ModelRule"})
            elif len(err) == 2:
                errors.append({"field": err[0], "message": err[1], "code": "ModelRule"})
            elif len(err) == 3:
                errors.append({"field": err[0], "message": err[1], "code": err[2]})
            else:
                raise TypeError(f"Invalid tuple length from __monk_validate__: {err}. Expected 1, 2, or 3 items.")
        else:
            raise TypeError(f"Invalid item yielded/returned from __monk_validate__: {err}. Expected a string or tuple.")


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
        value = object.__getattribute__(instance, field_name)
        rule_tuple = rules.get(field_name)

        if rule_tuple:
            constraints, is_nullable, is_not_null, not_null_c = rule_tuple

            if value is None:
                if not is_nullable and (is_not_null or not settings.default_allow_none):
                    msg = getattr(not_null_c, "message", None) or "Field is required and cannot be null."
                    code = getattr(not_null_c, "code", None) or "NotNull"
                    errors.append({"field": field_name, "message": msg, "code": code})
                continue

            for c in constraints:
                try:
                    c.validate(value)
                except ValidationError as e:
                    for err in e.errors:
                        err["field"] = f"{field_name}{err.get('field', '')}"
                        errors.append(err)
                except (ValueError, TypeError) as e:
                    error_code = getattr(c, "code", None) or type(c).__name__
                    errors.append({"field": field_name, "message": str(e), "code": error_code})

            if type(value) not in _PRIMITIVE_TYPES:
                _recurse(value, field_name, errors)
        elif type(value) not in _PRIMITIVE_TYPES:
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
