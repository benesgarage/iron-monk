# Advanced Usage

## Custom Error Messages
Every built-in constraint supports an optional `message` argument. `iron-monk` uses string formatting to allow you to dynamically inject the invalid `{value}` or constraint parameters.

You can even interpolate properties of an inner constraint when using `Not` by accessing `{constraint.property_name}`.

```python
from typing import Annotated

from monk import monk
from monk.constraints import Interval, Not

@monk
class Registration:
    # 1. Simple interpolation with {value} and constraint parameters like {ge}
    age: Annotated[
        int,
        Interval(ge=18, message="You are {value}, but must be at least {ge}!")
    ]
    # 2. Nested interpolation (interpolating properties of the inner constraint)
    forbidden_number: Annotated[
        int, 
        Not(
            Interval(ge=5, le=10),
            message="You picked {value}, but numbers between {constraint.ge} and {constraint.le} are forbidden!"
        )
    ]
```

## Custom Error Codes

By default, the code field in the `ErrorDict` evaluates to the exact name of the constraint class that failed (e.g., "Interval" or "Email").

Many APIs often need to return specific, machine-readable error codes so frontend apps can map them to translation dictionaries or specific UI states. Every built-in constraint supports an optional code argument to override this behavior.
```python
from typing import Annotated

from monk import monk
from monk.constraints import Interval, Len

@monk
class Registration:
    # 1. Will return code: "Interval"
    score: Annotated[int, Interval(ge=0)]

    # 2. Will return code: "USER_UNDERAGE"
    age: Annotated[int, Interval(ge=18, code="USER_UNDERAGE")]
    
    # 3. Will return code: "INVALID_PIN"
    pin: Annotated[str, Len(min_len=4, code="INVALID_PIN")]
```


## Cross-Field Validation
Sometimes a validation rule depends on multiple fields at once (e.g., `password` must equal `password_confirm`, or `end_date` must be after `start_date`).

To handle this, `iron-monk` provides the `__monk_validate__` hook. This method is executed automatically only if all individual field-level constraints pass successfully.

```python
from collections.abc import Iterator

from monk import monk
from monk.types import MonkError

# 1. Return an iterator, this can be any iterable (list, generator, etc.)
@monk
class Registration:
    password: str
    password_confirm: str
    age: int

    def __monk_validate__(self) -> Iterator[MonkError] | None:
        # String (or 1-Tuple) for a model-wide "root" error
        if self.password == "admin" and self.age < 18:
            yield "Young users cannot use the admin password."
            
        # 2-Tuple (field, message)
        if self.password != self.password_confirm:
            yield "password_confirm", "Passwords do not match."
        
        # 3-Tuple (field, message, constraint_name)
        if self.password == "superuser" and self.age < 21:
            yield "age", "Superusers must be over 21", "YoungSuperUser"


# 2. Return a string
@monk 
class Login:
    username: str

    def __monk_validate__(self) -> MonkError | None:
        if self.username == "admin":
            return "Admin login is disabled."
```

## Custom Constraints
Constraints in `iron-monk` use duck-typing. You do not need to inherit from any base classes.

A valid constraint is just a class with a `validate(self, value: Any) -> None` method that raises a `ValueError` or `TypeError`.

```python
class IsEven:
    def validate(self, value: Any) -> None:
        try:
            if value % 2 != 0:
                raise ValueError("Must be an even number.")
        except TypeError:
            raise TypeError("Must be a number.")
```

### The `@constraint` Decorator

To give your constraint support for initialization parameters and **Custom Error Messages** (with interpolation) by using the `@constraint` decorator.

```python
from typing import Any

from monk import constraint

@constraint
class DivisibleBy:
    divisor: int
    # The decorator handles the rest!
    def validate(self, value: Any) -> None:
        try:
            if value % self.divisor != 0:
                raise ValueError(f"Must be divisible by {self.divisor}")
        except TypeError:
            raise TypeError("Must be a number.")
```