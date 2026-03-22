# Beartype

> https://github.com/beartype/beartype

Stack `iron-monk` with `beartype` to combine instant runtime type-checking with comprehensive business logic validation.

## The Integration

```python
from typing import Annotated
from beartype import beartype
from beartype.roar import BeartypeCallHintParamViolation
from monk import monk, validate
from monk.constraints import Email, Interval
from monk.exceptions import ValidationError

# Stack the decorators
@beartype
@monk
class User:
    email: Annotated[str, Email]
    age: Annotated[int, Interval(ge=18)]

# 1. Type Checking (Caught instantly by beartype)
try:
    User(email="test@domain.com", age="twenty")
except BeartypeCallHintParamViolation:
    print("Type Error Caught!")

# 2. Value Validation (Caught explicitly by iron-monk)
try:
    validate(User(email="bad-email", age=12))
except ValidationError as e:
    print(e.flatten())
    # ['email: Must be a valid email address.', 'age: Must be greater than or equal to 18.']
```

### Delegating Nullability

To let `beartype` exclusively handle required vs. optional fields (`| None`), configure `iron-monk` to allow `None` values globally.

```python
from monk import settings
settings.default_allow_none = True
```

### The Global Import Hook

If using `beartype`'s global import hook, you don't need to stack decorators. `iron-monk` dataclasses are type-checked automatically.

```python
from beartype.claw import beartype_this_package
beartype_this_package()
```
