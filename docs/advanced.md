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

```python
@monk
class Registration:
    age: Annotated[
        int, 
        Interval(ge=18, message="You are {value}, but must be at least {ge}!")
    ]
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