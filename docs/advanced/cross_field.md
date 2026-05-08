# Cross-Field Validation

Some rules cannot live on a single field — they only make sense relative to siblings. `iron-monk` exposes two complementary tools:

| Tool | Style | Use it when |
| --- | --- | --- |
| **`Ref(...)`** | Declarative — lives inside the constraint that owns the error. | Field B's bounds, equality, or membership depend on Field A. The check is naturally directional. |
| **`__monk_validate__`** | Programmatic — a method on the class. | The rule is symmetric, spans 3+ fields, or needs Python logic that does not fit a constraint. |

You can use either or both. They run in a defined order (Refs first, then `__monk_validate__`) and aggregate into the same `ValidationError`.

---

## `Ref` — Declarative Cross-Field Rules

`Ref("field_name")` is a marker. When a constraint receives a `Ref`, `iron-monk` resolves it to the sibling field's value at validation time, then injects it into the constraint before evaluation.

The reference is compiled once at decoration time into a blueprint, so runtime cost is the same as a constant value. The original constraint instance is never mutated — a clone is built per call, preserving thread safety.

### Equality and inversion

```python
from typing import Annotated
from monk import monk
from monk.constraints import Eq, Not, Ref

@monk
class Registration:
    password: str
    confirm_password: Annotated[str, Eq(Ref("password"))]

@monk
class ChangePassword:
    old_password: str
    new_password: Annotated[str, Not(Eq(Ref("old_password")))]
```

### Dynamic bounds

```python
from typing import Annotated
from monk import monk
from monk.constraints import Interval, Len, Ref

@monk
class AuctionBid:
    starting_price: float
    offer: Annotated[float, Interval(gt=Ref("starting_price"))]

@monk
class CreateWorkspace:
    plan_max_users: int
    invited_users: Annotated[list[str], Len(max_len=Ref("plan_max_users"))]
```

### Dynamic membership

Validate inputs against lists supplied elsewhere in the same payload — useful when the API echoes back a menu the client must choose from.

```python
from typing import Annotated
from monk import monk
from monk.constraints import OneOf, Subset, Ref

@monk
class PizzaOrder:
    available_toppings: list[str]
    chosen_toppings: Annotated[list[str], Subset(Ref("available_toppings"))]

@monk
class Election:
    nominees: list[str]
    winner: Annotated[str, OneOf(Ref("nominees"))]
```

### Refs inside containers

The blueprint compiler is recursive. `Ref` works inside nested containers, dictionary keys, and logical wrappers.

```python
from typing import Any, Annotated
from monk import monk
from monk.constraints import ContainsKeys, Ref

@monk
class ConfigValidator:
    required_fields: list[str]
    config_data: Annotated[dict[str, Any], ContainsKeys(Ref("required_fields"))]
```

### Ref-aware constraints

The following built-ins accept `Ref` for at least one constructor argument:

`Eq`, `Interval` (all bounds), `Len` (`min_len`, `max_len`), `ExactLen`, `MultipleOf`, `StartsWith`, `EndsWith`, `Contains`, `OneOf`, `Subset`, `ContainsKeys`, `CSV`, `DictOf`, `AnyOf`, `AllOf`, `Not`.

Custom constraints can opt in by accepting `Ref | <real type>` on the relevant argument; see **[Customization](customization.md)**.

---

## `__monk_validate__` — Programmatic Hook

For rules that do not fit a single constraint (multi-field invariants, conditional logic, expensive computations), implement `__monk_validate__` on the class.

The hook runs **after** all field-level constraints have passed — so you never have to defend against bad inputs on individual fields.

### Yielding multiple errors

`yield` an iterator of errors. Each entry is a string, 2-tuple, or 3-tuple:

| Form | Meaning |
| --- | --- |
| `"message"` | Model-wide error (no specific field). |
| `("field", "message")` | Field-specific error using the default code. |
| `("field", "message", "CODE")` | Field-specific error with custom code. |

```python
from collections.abc import Iterator
from monk import monk
from monk.types import MonkError

@monk
class Registration:
    password: str
    password_confirm: str
    age: int

    def __monk_validate__(self) -> Iterator[MonkError] | None:
        if self.password == "admin" and self.age < 18:
            yield "Young users cannot use the admin password."

        if self.password != self.password_confirm:
            yield "password_confirm", "Passwords do not match."

        if self.password == "superuser" and self.age < 21:
            yield "age", "Superusers must be over 21", "YoungSuperUser"
```

### Returning a single error

If you have one rule that either passes or fails, `return` a single error instead of yielding:

```python
from monk import monk
from monk.types import MonkError

@monk
class Login:
    username: str

    def __monk_validate__(self) -> MonkError | None:
        if self.username == "admin":
            return "Admin login is disabled."
```

### When to prefer which

- Reach for **`Ref`** first. It puts the error on the right field and survives schema refactors better.
- Reach for **`__monk_validate__`** when the rule spans many fields, the logic is expensive, or you need conditional flow that does not compose as a constraint.
