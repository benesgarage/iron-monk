# Custom Constraints & Errors

## Custom Error Messages
Use the `message` argument to override default errors. You can dynamically inject the invalid `{value}` or constraint parameters (like `{ge}`). When using `Not`, interpolate inner properties using `{constraint.property_name}`.

```python
from typing import Annotated
from monk import monk
from monk.constraints import Interval, Not

@monk
class Registration:
    age: Annotated[
        int,
        Interval(ge=18, message="You are {value}, but must be at least {ge}!")
    ]
    
    forbidden_number: Annotated[
        int, 
        Not(Interval(ge=5, le=10), message="You picked {value}, forbidden range: {constraint.ge}-{constraint.le}")
    ]
```

## Custom Error Codes

By default, the error code matches the constraint's class name (e.g., "Interval"). Override it using the code argument to return specific, machine-readable identifiers for your API.

```python
from typing import Annotated
from monk import monk
from monk.constraints import Interval, Len

@monk
class Registration:
    score: Annotated[int, Interval(ge=0)] # code: "Interval"
    age: Annotated[int, Interval(ge=18, code="USER_UNDERAGE")] # code: "USER_UNDERAGE"
    pin: Annotated[str, Len(min_len=4, code="INVALID_PIN")] # code: "INVALID_PIN"
```

## Custom Constraints
`iron-monk` uses duck-typing. A valid constraint is any `class` with a `validate(self, value: Any) -> None` method that raises a `ValueError` or `TypeError`.

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

### The `@constraint` Decorator

Use the @constraint decorator to instantly add support for initialization parameters and custom message interpolation to your custom rules.

```python
from typing import Any
from monk import constraint

@constraint
class DivisibleBy:
    divisor: int
    
    def validate(self, value: Any) -> None:
        try:
            if value % self.divisor != 0:
                raise ValueError(f"Must be divisible by {self.divisor}")
        except TypeError:
            raise TypeError("Must be a number.")
```