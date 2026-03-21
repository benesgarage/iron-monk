# Beartype

[beartype](https://github.com/beartype/beartype) is a fast runtime type checker for Python. 

Because `iron-monk` intentionally avoids doing deep runtime type-checking (focusing entirely on *value validation* and *business constraints*), it pairs flawlessly with `beartype`. 

By stacking their decorators, you get the ultimate fortress: `beartype` strictly enforces your Python type hints instantly, and `iron-monk` comprehensively aggregates your business logic errors into clean, API-ready payloads.

## The Integration

```python
from typing import Annotated
from beartype import beartype
from beartype.roar import BeartypeCallHintParamViolation

from monk import monk, validate
from monk.constraints import Email, Interval
from monk.exceptions import ValidationError

# 1. Stack the decorators!
@beartype
@monk
class User:
    email: Annotated[str, Email]
    age: Annotated[int, Interval(ge=18)]


# 2. Type Checking (beartype catches this instantly)
try:
    User(email="test@domain.com", age="twenty")
except BeartypeCallHintParamViolation as e:
    print("Type Error Caught!")

# 3. Value Validation (iron-monk catches this explicitly)
try:
    # Types are correct, but values break the business rules
    user = User(email="bad-email", age=12)
    validate(user)
except ValidationError as e:
    print(e.flatten())
    # Output: ['email: Must be a valid email address.', 'age: Must be greater than or equal to 18.']
```

### Delegating Nullability

If you want `beartype` to be the *sole* enforcer of required vs. optional fields, you can tell `iron-monk` to globally allow `None` values. This stops `iron-monk` from throwing `NotNull` errors, letting `beartype` handle missing data according to your `| None` type hints.

```python
from monk import settings
settings.default_allow_none = True
```

### The Global Import Hook
If you are using beartype's global import hook (`beartype.claw`), you don't even need to stack the decorators! `iron-monk`'s dataclasses are automatically type-checked alongside the rest of your application invisibly.
```python
from beartype.claw import beartype_this_package
beartype_this_package()
```
