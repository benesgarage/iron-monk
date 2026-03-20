# Advanced Usage

## The Lifecycle

When you decorate a class with `@monk`, it alters the lifecycle of the object to protect your application from invalid data.

### 1. Instantiation
When you instantiate a Monk object, validation does **not** happen immediately (unless Fail-Fast is enabled).

```python
user = User(email="bad-email", age=12)
print(user.email) # ❌ Raises UnvalidatedAccessError!
```

### 2. Validation
When you are ready to validate the data, explicitly call the `validate()` function.

```python
from monk import validate

try:
    valid_user = validate(user)
except ValidationError as e:
    print(e.errors) 
```

### 3. Safe Access
Once `validate()` succeeds, the object is ready for use. It behaves exactly like a standard, high-performance Python dataclass, and all attributes are safely accessible.

## Handling Errors

When validation fails, `iron-monk` raises a `ValidationError`. This exception contains all the accumulated errors across your dataclass.

You can extract these errors in two ways depending on your use case:

1. Structured Data (`e.errors`): Returns a `list` of `ErrorDict` objects (a `TypedDict` containing `field`, `message`, and `constraint`).
2. Flattened Strings (`e.flatten()`): Returns a `list` of formatted `{field}: {message}` strings. This is useful for CLI tools, console printouts, or basic application logging.

```python
from typing import Annotated

from monk import monk, validate
from monk.constraints import Email, Interval
from monk.exceptions import ValidationError

@monk
class User:
    email: Annotated[str, Email]
    age: Annotated[int, Interval(ge=18)]

user = User(email="bad-email", age=12)

try: 
    validate(user)
except ValidationError as e: 
    # 1. Structured Data
    print(e.errors[0]["field"]) # "email"
    print(e.errors[0]["message"])  # "Must be a valid email address."
    
    # 2. Flattened Strings
    print(e.flatten())
    # [
    #   "email: Must be a valid email address.", 
    #   "age: Must be greater than or equal to 18."
    # ]
```

## Fail-Fast Mode
By default, `iron-monk` defers validation until you explicitly call `validate(obj)`. If you prefer the traditional "crash on init" behavior of frameworks like Pydantic, you can disable defer mode.

**1. Globally via Environment Variable:**
```sh
export MONK_DEFER=false
```

**2. Globally via Code:**
```python
from monk import settings
settings.defer = False
```

**3. Per-Class Override:**
```python
from typing import  Annotated

from monk import monk
from monk.constraints import StartsWith

@monk(defer=False)
class Headers:
    authorization: Annotated[str, StartsWith("Bearer ")]
```

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
        if value is None: return
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
        if value is None: return
        try:
            if value % self.divisor != 0:
                raise ValueError(f"Must be divisible by {self.divisor}")
        except TypeError:
            raise TypeError("Must be a number.")
```