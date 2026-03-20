# Advanced Usage

## The Lifecycle

When you decorate a class with `@monk`, it alters the lifecycle of the object to protect your application from invalid data.

### 1. Instantiation (The Quarantine)
When you instantiate a Monk object, validation does **not** happen immediately (unless Fail-Fast is enabled). Instead, the object is placed in a "Guarded" state. If you try to access an attribute on a guarded object, it will raise an `UnvalidatedAccessError`.

```python
user = User(email="bad-email", age=12)
print(user.email) # ❌ Raises UnvalidatedAccessError!
```

### 2. Validation
When you are ready to validate the data, explicitly call the `validate()` function. This evaluates all constraints. If it fails, it raises a structured `ValidationError`.

```python
try:
    valid_user = validate(user)
except ValidationError as e:
    print(e.errors) 
```

### 3. Safe Access
Once `validate()` succeeds, the object is "uncloaked". It behaves exactly like a standard, high-performance Python dataclass, and all attributes are safely accessible.

## Fail-Fast Mode
By default, `iron-monk` defers validation until you explicitly call `validate(obj)`. If you prefer the traditional "crash on init" behavior of frameworks like Pydantic, you can enable Fail-Fast mode.

**1. Globally via Environment Variable:**
```sh
export MONK_DEFERRED_VALIDATION=false
```

**2. Globally via Code:**
```python
from monk import settings
settings.deferred_validation = False
```

**3. Per-Class Override:**
```python
@monk(deferred_validation=False)
class Headers:
    authorization: Annotated[str, StartsWith("Bearer ")]
```

## Custom Error Messages
Every built-in constraint supports an optional `message` argument. `iron-monk` uses safe string formatting to allow you to dynamically inject the invalid `{value}` or constraint parameters!
You can even interpolate properties of an inner constraint when using `Not` by accessing `{constraint.property_name}`.

```python
from typing import Annotated

from monk import monk
from monk.constraints import Interval, Not

@monk
class Registration:
    # 1. Simple interpolation with {value} and constraint parameters like {ge}
    age: Annotated[ int, Interval(ge=18, message="You are {value}, but must be at least {ge}!") ]
    # 2. Nested interpolation (interpolating properties of the inner constraint)
    forbidden_number: Annotated[
        int, 
        Not(Interval(ge=5, le=10), message="You picked {value}, but numbers between {constraint.ge} and {constraint.le} are forbidden!")
    ]
```

## Custom Error Messages
Every built-in constraint supports an optional `message` argument. `iron-monk` uses safe string formatting to allow you to dynamically inject the invalid `{value}` or constraint parameters!

```python
@monk
class Registration:
    age: Annotated[
        int, 
        Interval(ge=18, message="You are {value}, but must be at least {ge}!")
    ]
```

## Model-Level (Cross-Field) Validation
Sometimes a validation rule depends on multiple fields at once (e.g., `password` must equal `password_confirm`, or `end_date` must be after `start_date`).
To handle this natively without polluting your dataclass's public API, `iron-monk` provides the `monk_validate` hook. This method is executed automatically only if all individual field-level constraints pass successfully.
To make validation as frictionless as possible, you can `return` or `yield` errors in several flexible formats using the `MonkError` type alias:

- String: A model-wide "root" error. 
- 2-Tuple (`field`, `message`): Targets a specific field.
- 3-Tuple (`field`, `message`, `constraint_name`): Targets a specific field and overrides the constraint name.
- 
Here are the three most common ways to structure your validation method:

### The Generator Way
When you need to perform multiple validation checks, simply `yield` an error back to `iron-monk`.

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
        # 1. Yield a 2-tuple to target a specific field
        if self.password != self.password_confirm:
            yield "password_confirm", "Passwords do not match."
    
        # 2. Yield a string for a generic "root" error
        if self.password == "admin" and self.age < 18:
            yield "Young users cannot use the admin password."
```

### The Return List Way
If you prefer to build a `list` of errors and return them all at once, `iron-monk` natively handles standard iterables.

```python
from monk import monk
from monk.types import MonkError

@monk
class Event:
    start: int
    end: int

    def __monk_validate__(self) -> list[MonkError] | None:
        errors = []
        if self.start > self.end:
            # You can append 3-tuples to override the constraint name!
            errors.append(("end", "End date must be after start date.", "DateLogic"))
        return errors if errors else None
```

### The Single Return Way
If your model only has one possible cross-field error, you can just `return` it directly without wrapping it in a `list` or yielding.

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


## Custom Constraints
Constraints in `iron-monk` use pure duck-typing. You do not need to inherit from any base classes.

A valid constraint is just a class with a `validate(self, field: str, value: Any) -> None` method that raises a `ValueError` or `TypeError`.

```python
class IsEven:
    def validate(self, field: str, value: Any) -> None:
        if value is None: return
        try:
            if value % 2 != 0:
                raise ValueError("Must be an even number.")
        except TypeError:
            raise TypeError("Must be a number.")
```

### The `@constraint` Decorator
If your custom constraint requires initialization parameters, wrap it in `@constraint`. 

This automatically generates a highly optimized frozen dataclass, and gives your custom constraint full support for **Custom Error Messages** (with interpolation) completely for free!

```python
from monk import constraint

@constraint
class DivisibleBy:
    divisor: int
    # The decorator handles the rest!
```