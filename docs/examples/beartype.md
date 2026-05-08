# beartype

Stack `iron-monk` with `beartype` to get instant runtime type-checking *and* business-logic validation. `beartype` enforces "Is this an `int`?"; `iron-monk` enforces "Is this `int` between 0 and 100?".

Project: <https://github.com/beartype/beartype>

## The integration

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

# Type checking — caught by beartype
try:
    User(email="test@domain.com", age="twenty")
except BeartypeCallHintParamViolation:
    print("Type error caught.")

# Value validation — caught by iron-monk
try:
    validate(User(email="bad-email", age=12))
except ValidationError as e:
    print(e.flatten())
    # ['email: Must be a valid email address.', 'age: Must be greater than or equal to 18.']
```

## Delegating nullability

To let `beartype` exclusively handle required vs. optional fields (`| None`), configure `iron-monk` to allow `None` globally:

```python
from monk import settings
settings.default_allow_none = True
```

## The global import hook

With `beartype`'s global import hook, you do not need to stack decorators — `iron-monk` dataclasses are type-checked automatically:

```python
from beartype.claw import beartype_this_package
beartype_this_package()
```
