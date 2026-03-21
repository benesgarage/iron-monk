# Core Concepts

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

1. **Structured Data (`e.errors`)**: Returns a `list` of `ErrorDict` objects (a `TypedDict` containing `field`, `message`, and `code`).
2. **Flattened Strings (`e.flatten()`)**: Returns a `list` of formatted `{field}: {message}` strings. This is useful for CLI tools, console printouts, or basic application logging.

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

## Required vs. Optional Fields

In `iron-monk`, validation logic is driven purely by your explicitly defined constraints, not by guessing your type hints. 

By default, if a field has constraints, it is treated as **required**. If it receives `None`, it will fail with a `NotNull` code. To explicitly allow `None` values, use the `Nullable` constraint marker.

```python
from typing import Annotated
from monk import monk
from monk.constraints import Email, Each, Nullable, NotNull, Len

@monk
class Profile:
    # 1. Strictly Required. Passing None will fail with NotNull!
    email: Annotated[str, Email]
    
    # 2. Top-Level Optional. Passing None is perfectly safe.
    nickname: Annotated[str | None, Nullable, Len(max_len=10)] = None

    # 3. Nested Optional. A list of strings where individual items can be None.
    tags: Annotated[list[str | None], Each(Nullable, Len(max_len=5))]
```

### Relying on Runtime Type Checkers

If you are using a runtime type checker (like `beartype` or `typeguard`) to enforce required fields, having `iron-monk` also enforce them can feel redundant. You can configure `iron-monk` to **allow `None` by default** globally. 

When this is enabled, the engine acts purely as a "value validator" and safely skips constraints on missing data. You can then use the `NotNull` marker if you want `iron-monk` to specifically enforce presence.

**Globally via Environment Variable:**
```sh
export MONK_DEFAULT_ALLOW_NONE=true
```

**Globally via Code:**
```python
from monk import settings
settings.default_allow_none = True
```

### Customizing the "Required" Error
Even if you are using the default behavior (where fields are required by default without needing markers), you can explicitly include the `NotNull` constraint just to override the default error message or code when a value is missing.

```python
from monk import monk
from monk.constraints import NotNull

@monk
class CustomRequired:
    # Overrides the default "Field is required and cannot be null." message
    email: Annotated[
        str, 
        NotNull(message="We really need your email!", code="MISSING_EMAIL"),
        Email,
    ]
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
from typing import Annotated
from monk import monk
from monk.constraints import StartsWith

@monk(defer=False)
class Headers:
    authorization: Annotated[str, StartsWith("Bearer ")]
```