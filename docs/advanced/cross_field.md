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

## Conditional Cross-Field Rules — `When` and `Switch`

Sometimes a sibling does not just *parameterize* a constraint — it determines whether the constraint applies at all. `When` and `Switch` are declarative wrappers built on the same blueprint compiler as `Ref`, so they pay no extra runtime cost and inherit recursive resolution.

### `When` — two-branch conditionals

`When(field, test, then, else_=None)` resolves `field` (a `Ref` to a sibling), runs `test` against the resolved value, and applies `then` to the **current** field's value if `test` passes. If `test` fails and `else_` is provided, `else_` is applied instead; otherwise the current field is unchecked.

```python
from typing import Annotated
from monk import monk
from monk.constraints import Eq, Len, Ref, When

@monk
class Order:
    payment_method: str
    cc_number: Annotated[
        str,
        When(field=Ref("payment_method"), test=Eq("credit"), then=Len(min_len=16, max_len=16)),
    ]
```

When `payment_method == "credit"`, the credit-card length rule applies; otherwise `cc_number` is unchecked. Add `else_` to enforce a fallback shape:

```python
@monk
class Profile:
    kind: str
    handle: Annotated[
        str,
        When(field=Ref("kind"), test=Eq("admin"), then=Len(min_len=8), else_=Len(min_len=3)),
    ]
```

`test`, `then`, and `else_` accept any constraint — bare classes (auto-instantiated), composed constraints (`AnyOf`, `AllOf`, `Not`), or container constraints (`Each`, `DictOf`).

### `Switch` — multi-branch dispatch

When more than two branches key off a discriminator, chained `When` becomes noisy. `Switch(field, cases, default=None)` is the typed sugar for that pattern — pass a mapping from discriminator values to constraints.

```python
from typing import Annotated
from monk import monk
from monk.constraints import Email, Len, Match, Ref, Switch

@monk
class Notification:
    channel: str  # "email" | "sms" | "push"
    target: Annotated[
        str,
        Switch(
            field=Ref("channel"),
            cases={
                "email": Email,
                "sms": Match(r"^\+\d+$"),
                "push": Len(min_len=64),
            },
        ),
    ]
```

If `channel` does not match any case, validation fails with `"No case matches discriminator ..."`. Provide `default=` to supply a catch-all:

```python
target: Annotated[str, Switch(field=Ref("channel"), cases={...}, default=Len(min_len=1))]
```

`Switch` is strict by design: an unknown discriminator without a `default` is an error. This makes discriminated unions structurally exhaustive, mirroring how `match` statements behave.

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
