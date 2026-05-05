# Asymmetric Validation (Cross-Field Dependencies)

A common challenge in data validation is when **Field B's rules change based on Field A, but Field A is completely independent of Field B.** This is known as an asymmetric (or directional) relationship.

While other validation libraries force you to write imperative, model-wide custom methods to handle these checks, `iron-monk` allows you to express them **declaratively** right on the field itself using the `Ref` keyword.

By keeping the validation logic co-located with the field that actually owns the error, your code remains clean, self-documenting, and incredibly fast.

## The `Ref` Keyword

The `Ref` object acts as a dynamic marker. When you pass `Ref("field_name")` into a constraint, `iron-monk` will automatically fetch the value of that sibling field at runtime and inject it into the constraint before evaluation.

Under the hood, `iron-monk` compiles these references into an AST Blueprint during startup. This guarantees **zero runtime compilation overhead** and strictly preserves thread safety.

---

## Real-World Examples

### 1. Directional State Matching (Equality)
The classic password confirmation. The `password` field is the source of truth, and the `confirm_password` field strictly depends on it.

```python
from typing import Annotated
from monk import monk, validate
from monk.constraints import Eq, Ref

@monk
class Registration:
    password: str
    confirm_password: Annotated[str, Eq(Ref("password"))]

user = Registration(password="SuperSecret!", confirm_password="SuperSecret!")
validate(user)
```

You can also compose `Ref` with logical operators like `Not`:
```python
from typing import Annotated

from monk import monk
from monk.constraints import Not, Eq, Ref

@monk
class ChangePassword:
    old_password: str
    new_password: Annotated[str, Not(Eq(Ref("old_password")))]
```

### 2. Dynamic Bounds & Thresholds
Sometimes the acceptable *range* or *size* of a field is dictated by another field.

**Example: Auction Bidding**
A user's bid must be strictly higher than the starting price.
```python
from typing import Annotated

from monk import monk
from monk.constraints import Interval, Ref

@monk
class AuctionBid:
    starting_price: float
    offer: Annotated[float, Interval(gt=Ref("starting_price"))]
```

**Example: Plan-based Limits**
A user's subscription tier dictates the maximum length of a list they can submit.
```python
from typing import Annotated

from monk import monk
from monk.constraints import Len, Ref

@monk
class CreateWorkspace:
    plan_max_users: int
    invited_users: Annotated[list[str], Len(max_len=Ref("plan_max_users"))]
```

### 3. Dynamic Menus & Subsets
You can validate inputs against dynamic lists provided directly in the payload! This is incredibly powerful for APIs that tell the client what options are available, and structurally guarantee the client only sends back valid choices.

**Example: Choosing Toppings**
```python
from typing import Annotated

from monk import monk
from monk.constraints import Subset, Ref

@monk
class PizzaOrder:
    available_toppings: list[str]
    chosen_toppings: Annotated[list[str], Subset(Ref("available_toppings"))]
```

**Example: Elections (`OneOf`)**
```python
from typing import Annotated

from monk import monk
from monk.constraints import OneOf, Ref

@monk
class Election:
    nominees: list[str]
    winner: Annotated[str, OneOf(Ref("nominees"))]
```

### 4. Advanced Containment & Nested References
Because `iron-monk`'s blueprint compiler is deeply recursive, `Ref` works flawlessly even when buried inside nested containers or dictionary keys!

**Example: Dynamic Keys**
Require that a free-form configuration dictionary contains specific keys based on a sibling field.
```python
from typing import Any, Annotated

from monk import monk
from monk.constraints import ContainsKeys, Ref

@monk
class ConfigValidator:
    required_fields: list[str]
    config_data: Annotated[dict[str, Any], ContainsKeys(Ref("required_fields"))]
```