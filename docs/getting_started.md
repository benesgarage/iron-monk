# Getting Started


## Step 1: Installation

```bash
pip install iron-monk
```

!!! tip "Namespace"
    The package is published as `iron-monk` but imported as `monk`. Always `import monk` (or `from monk import ...`) in your code.

## Step 2: Annotate Your Types

`iron-monk` provides the same toolkit across every Python surface — classes, functions, methods, raw dicts, and even standalone calls.

=== "Dataclasses"
    ```python
    from typing import Annotated
    from monk import monk
    from monk.constraints import Email, Interval

    @monk # (1)!
    class User:
        email: Annotated[str, Email]
        age: Annotated[int, Interval(ge=18)]
    ```

    1. The `@monk` decorator on a `class` converts it to a `dataclass` and locks attribute access until validation runs (see Step 3).

=== "Functions"
    ```python
    from typing import Annotated
    from monk import monk
    from monk.constraints import Email, Interval

    @monk # (1)!
    def process_user(
        email: Annotated[str, Email],
        age: Annotated[int, Interval(ge=18)],
    ) -> None:
        ...
    ```

    1. The `@monk` decorator on a function wraps it; arguments are validated immediately on every call.

=== "Methods"
    ```python
    from typing import Annotated
    from monk import monk
    from monk.constraints import Email

    class NotificationService:
        @classmethod # (1)!
        @monk # (2)!
        def broadcast(cls, email: Annotated[str, Email]) -> None:
            ...
    ```

    1. `@classmethod` is shown here, but `@staticmethod` and instance methods work the same way. Always place `@monk` **below** the binding decorator.
    2. Arguments are validated immediately on every call, exactly like a free function.

=== "TypedDicts"
    ```python
    from typing import Annotated, TypedDict
    from monk.constraints import Email, Interval

    class UserDict(TypedDict): # (1)!
        email: Annotated[str, Email]
        age: Annotated[int, Interval(ge=18)]
    ```

    1. No decorator required — `iron-monk` reads constraints directly off the `TypedDict`. A `@monk` dataclass also works as a schema target.

=== "Standalone"
    ```python
    from monk import validate_value # (1)!
    from monk.constraints import Email, Len
    ```

    1. `validate_value(value, *constraints)` runs one or more constraints against a single value. No class needed — useful for controllers, scripts, and one-shot checks (see Step 3). Every constraint also exposes a raw `.validate(value)` method for direct use.

---

## Step 3: Validate

`iron-monk` aggregates **every** field-level error into a single `ValidationError`. It does not fail-fast — pass an object with two bad fields and you get two errors back, not one.

`ValidationError.errors` is a `list[ErrorDict]` of `{field, message, code}`. Two helpers are available on every error:

- `.flatten()` — flat `["field: message", ...]` strings.
- `.to_rfc7807()` — RFC 7807 problem-detail dict for HTTP APIs.

=== "Dataclasses"
    ```python
    from monk import validate
    from monk.exceptions import ValidationError

    user = User(email="bad-email", age=12) # (1)!

    try:
        validate(user) # (2)!
    except ValidationError as e:
        print(len(e.errors)) # 2  (3)!

    # Happy path
    good = validate(User(email="kai@example.com", age=30))
    print(good.email) # (4)!
    ```

    1. Instantiation is instant. By default, `iron-monk` defers validation until you call `validate()` — attribute access on an unvalidated instance raises `UnvalidatedAccessError`. Use `@monk(defer=False)` for fail-on-construct semantics.
    2. Both `email` and `age` are invalid; both errors are collected.
    3. Two errors, not one — `iron-monk` never fails fast.
    4. After successful validation, attribute access is unlocked.

=== "Functions"
    ```python
    from monk.exceptions import ValidationError

    try:
        process_user(email="bad-email", age=12) # (1)!
    except ValidationError as e:
        print(len(e.errors)) # 2

    process_user(email="kai@example.com", age=30) # (2)!
    ```

    1. Function arguments are validated eagerly on call.
    2. Valid input — no exception, function runs normally.

=== "Methods"
    ```python
    from monk.exceptions import ValidationError

    try:
        NotificationService.broadcast(email="bad-email")
    except ValidationError as e:
        print(e.flatten()) # ['email: Must be a valid email address.']

    NotificationService.broadcast(email="kai@example.com") # (1)!
    ```

    1. Methods validate exactly like free functions.

=== "TypedDicts"
    ```python
    from monk import validate_dict
    from monk.exceptions import ValidationError

    try:
        validate_dict({"email": "bad-email", "age": 12}, UserDict) # (1)!
    except ValidationError as e:
        print(len(e.errors)) # 2

    validate_dict({"email": "kai@example.com", "age": 30}, UserDict) # (2)!
    ```

    1. No object instantiation — `iron-monk` walks the raw dict against the schema.
    2. Returns the validated dict on success. Pass `partial=True` for PATCH-style payloads or `drop_extra_keys=True` to strip unknown keys.

=== "Standalone"
    ```python
    from monk import validate_value
    from monk.constraints import Email, Len
    from monk.exceptions import ValidationError

    try:
        validate_value("X", Len(min_len=3), Email) # (1)!
    except ValidationError as e:
        print(len(e.errors)) # 2  (2)!

    validate_value("kai@example.com", Email) # (3)!

    # Lower-level: skip aggregation, raise native ValueError/TypeError
    Email().validate("bad-email") # (4)!
    ```

    1. `validate_value` aggregates every per-constraint failure into a single `ValidationError` (same semantics as `validate()`). Use `field_name="..."` to customize the field label in `e.flatten()` output.
    2. Both `Len` and `Email` fail — both errors collected, no fail-fast.
    3. Happy path. Returns `None`; raises only on failure.
    4. For raw single-constraint checks where aggregation is not needed, call the constraint's `.validate()` directly — it raises native `ValueError` / `TypeError`.

---

## Next Steps

- **[Core Concepts](concepts/index.md)** — the validation lifecycle, defer semantics, and error model.
- **[Constraints Toolkit](constraints/index.md)** — the full catalog of built-in constraints.
- **[Advanced Usage](advanced/index.md)** — cross-field rules, custom constraints, and framework integration.
