# Customization

`iron-monk` exposes three customization layers, ordered from cheapest to most powerful:

1. **Custom messages and codes** — change the error string or code on any built-in constraint.
2. **Custom message templates** — use placeholders to weave the offending value or constraint parameters into the message.
3. **Custom constraints** — write your own rule in three lines.

The first two also work on user-defined constraints out of the box.

---

## Custom Messages and Codes

Every built-in constraint accepts `message=` and `code=`:

```python
from typing import Annotated
from monk import monk
from monk.constraints import Interval, Len

@monk
class Registration:
    score: Annotated[int, Interval(ge=0)]                                # default code: "Interval"
    age:   Annotated[int, Interval(ge=18, code="USER_UNDERAGE")]         # custom code
    pin:   Annotated[str, Len(min_len=4, message="PIN too short.")]      # custom message
```

`code` is the machine-readable identifier exposed to clients via `e.errors[i]["code"]`. Set stable, screaming-snake-case codes for anything a frontend needs to branch on.

---

## Message Templates

Messages support Python `str.format` placeholders. Two kinds resolve at runtime:

- **`{value}`** — the value that failed validation.
- **`{<field_name>}`** — any constructor argument on the constraint instance (e.g. `{ge}` for `Interval(ge=18)`, `{prefix}` for `StartsWith("cat_")`).

Inside `Not(...)`, the inner constraint's parameters are accessible via `{constraint.<field_name>}`:

```python
from typing import Annotated
from monk import monk
from monk.constraints import Interval, Not

@monk
class Registration:
    age: Annotated[
        int,
        Interval(ge=18, message="You are {value}, but must be at least {ge}."),
    ]
    forbidden_number: Annotated[
        int,
        Not(
            Interval(ge=5, le=10),
            message="You picked {value}, forbidden range: {constraint.ge}-{constraint.le}.",
        ),
    ]
```

If a placeholder cannot be resolved, the literal template string is used as a fallback — your validation will not crash on a typo'd format key.

---

## Custom Constraints

The `MonkConstraint` protocol is one method:

```python
def validate(self, value: Any) -> None:
    ...
```

Anything with that method is a constraint. No registration, no metaclass, no inheritance. Raise `ValueError` for value problems and `TypeError` for shape problems — `iron-monk` will route them into the same `ValidationError` aggregation.

### The minimum viable constraint

```python
from typing import Any

class IsEven:
    def validate(self, value: Any) -> None:
        try:
            if value % 2 != 0:
                raise ValueError("Must be an even number.")
        except TypeError:
            raise TypeError("Must be a number.")
```

Use it like any built-in:

```python
from typing import Annotated
from monk import monk

@monk
class Box:
    count: Annotated[int, IsEven]
```

### `@constraint` — the recommended path

The `@constraint` decorator gives you, for free:

- A frozen, slotted dataclass (fast, hashable, thread-safe).
- Constructor parameters declared via class attributes.
- Automatic `message=` and `code=` support with format-placeholder interpolation.

```python
from typing import Any, Annotated
from monk import constraint, monk

@constraint
class DivisibleBy:
    divisor: int
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        try:
            if value % self.divisor != 0:
                raise ValueError(f"Must be divisible by {self.divisor}.")
        except TypeError:
            raise TypeError("Must be a number.")

@monk
class Order:
    pack_size: Annotated[int, DivisibleBy(divisor=12, message="Order in dozens (got {value}).")]
```

Declaring `message` and `code` as `str | None = None` is what makes the format-placeholder machinery kick in. Skip them if you do not need overrides.

### Accepting `Ref` for cross-field rules

Allow callers to pass a `Ref(...)` in place of a literal by widening the parameter type and resolving the reference inside `validate` (or by relying on `iron-monk`'s blueprint compiler — see **[Cross-Field Validation](cross_field.md)**).

```python
from typing import Any
from monk import constraint
from monk.constraints import Ref

@constraint
class GreaterThan:
    bound: int | Ref
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if value <= self.bound:
            raise ValueError(f"Must be greater than {self.bound}.")
```

When this constraint is attached to a field, `iron-monk` walks the constraint instance, finds the `Ref`, and clones the constraint per call with the resolved sibling value substituted for `bound`. No further wiring required.

### Aggregating errors from a custom constraint

If your constraint validates a collection, raising a `ValidationError` (instead of `ValueError`) lets you report multiple per-element errors at once:

```python
from typing import Any
from monk import constraint
from monk.exceptions import ValidationError

@constraint
class AllPositive:
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        errors = []
        for i, item in enumerate(value):
            if not isinstance(item, (int, float)) or item <= 0:
                errors.append({"field": f"[{i}]", "message": "Must be positive.", "code": "AllPositive"})
        if errors:
            raise ValidationError(errors)
```

The `field` paths you set are concatenated with the parent field name automatically.
