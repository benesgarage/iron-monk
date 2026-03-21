# Custom Constraints & Errors

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

To give your constraint support for initialization parameters and **Custom Error Messages** (with interpolation) use the `@constraint` decorator.

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