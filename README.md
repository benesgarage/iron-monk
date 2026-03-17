<div align="center">
  <a href="https://github.com/benesgarage/iron-monk">
    <img src="./assets/monk.png" width="400" alt="iron-monk logo" style="display: block; margin-bottom: 0; padding-bottom: 0;">
  </a>
  <h1 style="margin-top: 0; padding-top: 0;">iron-monk</h1>
  <h4>A minimalist, strict validation library for Python dataclasses.</h4>
</div>


[![CI/CD](https://img.shields.io/github/actions/workflow/status/benesgarage/iron-monk/ci.yml?branch=main&label=CI)](https://github.com/benesgarage/iron-monk/actions)
[![PyPI version](https://img.shields.io/pypi/v/iron-monk.svg?color=black)](https://pypi.org/project/iron-monk/)
[![Python Versions](https://img.shields.io/pypi/pyversions/iron-monk.svg?color=black)](https://pypi.org/project/iron-monk/)
[![License](https://img.shields.io/github/license/benesgarage/iron-monk?color=black)](https://github.com/benesgarage/iron-monk/blob/main/LICENSE)
[![Coverage: 100%](https://img.shields.io/badge/Coverage-100%25-brightgreen.svg?color=black)]()
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-0-success.svg?color=black)]()


## Installation

```bash
pip install iron-monk
```

```bash
# Or with modern package managers:
uv add iron-monk
poetry add iron-monk
```

## Quickstart

Define your models using the `@monk` decorator and wrap your types in `Annotated` constraints.

```python
from typing import Annotated
from monk import monk, validate
from monk.constraints import Email, Interval
from monk.exceptions import ValidationError

@monk
class User:
    email: Annotated[str, Email]
    age: Annotated[int, Interval(ge=18)]

# 1. Instantiate
user = User(email="bad-email", age=12)

# 2. Validate
try:
    validate(user)
except ValidationError as e:
    print(e.errors)
    # [{'field': 'email', 'message': "..."}, {'field': 'age', 'message': "..."}]

# 3. Use it safely
valid_user = validate(User(email="test@domain.com", age=25))
print(valid_user.email) # "test@domain.com"
```

> 💡 Looking for real-world usage? Check out the [examples](examples) directory to see how iron-monk integrates flawlessly with Strawberry GraphQL, Application Configuration, and more!

## Why iron-monk?
The Python ecosystem is dominated by heavy validation frameworks. iron-monk is built for a completely different philosophy:
- 🎯 **Scope**: Do one thing well. Unlike libraries that parse, coerce, and serialize, `iron-monk` focuses *strictly* on validation.
- 🪶 **Zero Dependencies**: Pure Python. No compiled Rust binaries or bloated environments.
- 🧬 **Zero Inheritance**: Just decorate a standard class with `@monk`. No massive base classes polluting your namespace.
- 🛡️ **Strict (No Magic)**: We don't secretly coerce the string `"123"` into the integer `123`.
- ⏳ **Deferred Validation**: Other frameworks force crashes on bad data. `iron-monk` captures it in a guarded state, giving *you* control over when validation occurs.

## The Constraint Toolkit

`iron-monk` comes fully equipped. All constraints elegantly handle `None` (nullability is left to the type checker) and throw native `TypeError`s if applied to incompatible data structures.

### Strings
```python
from typing import Annotated
from monk import monk
from monk.constraints import Match, StartsWith, EndsWith, LowerCase, UpperCase, IsDigit, IsAscii

@monk
class TextData:
    sku: Annotated[str, Match(r"^PROD-\d+$")]
    role: Annotated[str, StartsWith("admin_")]
    file_name: Annotated[str, EndsWith(".csv")]
    username: Annotated[str, LowerCase]
    department_code: Annotated[str, UpperCase]
    pin_code: Annotated[str, IsDigit]
    bio: Annotated[str, IsAscii]
```

### Numeric
```python
from typing import Annotated
from monk import monk
from monk.constraints import Interval, MultipleOf, NonNegative, IsFinite, IsNan, IsInfinite

@monk
class Metrics:
    percentage: Annotated[float, Interval(ge=0, le=100)] # 0 <= x <= 100
    batch_size: Annotated[int, MultipleOf(5)]
    count: Annotated[int, NonNegative]
    temperature: Annotated[float, IsFinite]
    missing_value: Annotated[float, IsNan]
    limit: Annotated[float, IsInfinite]
```

### Collections & Iterables
```python
from typing import Annotated
from monk import monk
from monk.constraints import Len, Contains, OneOf, Unique, Each, LowerCase

@monk
class Group:
    password: Annotated[str, Len(min_len=8, max_len=64)]
    tags: Annotated[list[str], Contains("admin")]
    status: Annotated[str, OneOf(["active", "pending", "closed"])]
    emails: Annotated[list[str], Unique]
    matrices: Annotated[list[list[int]], Unique] # Safely handles unhashable inner items!
    
    # Apply constraints to every element in a collection:
    usernames: Annotated[list[str], Each(LowerCase, Len(min_len=3))]
```

### Formats & Networking
```python
import uuid
from typing import Annotated
from monk import monk
from monk.constraints import Email, URL, IPAddress, UUID

@monk
class ServerNode:
    contact: Annotated[str, Email]
    webhook: Annotated[str, URL]
    public_ip: Annotated[str, IPAddress]
    session_id: Annotated[str | uuid.UUID, UUID]
```

### Logical & Time
```python
import datetime
from typing import Annotated
from monk import monk
from monk.constraints import Predicate, Not, Email, IsUTC

@monk
class Event:
    # Turn any boolean function into a constraint
    even_number: Annotated[int, Predicate(lambda x: x % 2 == 0)]
    # Invert any other constraint
    not_an_email: Annotated[str, Not(Email)]
    # Built-in timezone strictness
    created_at: Annotated[datetime.datetime, IsUTC]
```

## Advanced Features

### Deferred vs. Instant Validation (Fail-Fast)
By default, `iron-monk` defers validation, placing objects into a guarded state until `validate()` is explicitly called. 

If you prefer the traditional "fail-fast" behavior (where objects validate and crash instantly upon instantiation with a `ValidationError`), you have three ways to enable it:

**1. Per-Class**
```python
from typing import Annotated
from monk import monk
from monk.constraints import Email

@monk(deferred_validation=False)
class User:
    email: Annotated[str, Email]
    
user = User(email="bad") # Raises ValidationError instantly
```

**2. Global Configuration**
```python
from monk import settings

settings.deferred_validation = False # Applies to all @monk classes
```

**3. Environment Variable (Production Friendly)**
```bash
export MONK_DEFERRED_VALIDATION=false
```

### Deep Recursion
Nested models are natively supported and fully recursive. If validation fails deep within a tree of lists and dictionaries, the error payload dynamically builds the exact dot-notation path.

```python
from typing import Annotated
from monk import monk, validate
from monk.exceptions import ValidationError
from monk.constraints import OneOf

@monk
class Config:
    env: Annotated[str, OneOf(["dev", "prod"])]

@monk
class Server:
    configs: list[Config]

server = Server(configs=[Config(env="dev"), Config(env="TEST")])

try:
    validate(server)
except ValidationError as e:
    print(e.errors[0]["field"]) 
    # Output: "configs[1].env"
```

### Custom Constraints
Building your own constraints is stupidly simple thanks to pure duck-typing. You don't even need to inherit from a base class. Just write a `validate()` method and raise a standard `ValueError` or `TypeError`.

```python
from typing import Any, Annotated
from monk import monk

class IsEven:
    def validate(self, field: str, value: Any) -> None:
        if value is None:
            return
            
        try:
            if value % 2 != 0:
                raise ValueError("Must be an even number.")
        except TypeError:
            raise TypeError("Must be a number.")

# Use it!
@monk
class User:
    user_id: Annotated[int, IsEven]
```

If your constraint needs parameters, use our `@constraint` wrapper to instantly turn it into a high-performance dataclass!

```python
from typing import Any, Annotated
from monk import constraint, monk

@constraint # This is just a convenience decorator. This equates to `@dataclass(frozen=True, slots=True)`
class DivisibleBy:
    divisor: int

    def validate(self, field: str, value: Any) -> None:
        if value is None:
            return
            
        try:
            if value % self.divisor != 0:
                raise ValueError(f"Must be divisible by {self.divisor}.")
        except TypeError:
            raise TypeError("Must be a number.")

# Use it!
@monk
class User:
    user_id: Annotated[int, DivisibleBy(5)]
```

## License
MIT