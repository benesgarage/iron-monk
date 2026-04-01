# Core Concepts

## Ways to Validate

Validate data across your entire stack using the same constraint toolkit:

1. **Dataclasses (`@monk`)**: Build DTOs with deferred validation and locked attribute access.
2. **Functions & Methods (`@monk`)**: Instantly validate incoming arguments and return values.
3. **Raw Dictionaries (`validate_dict`)**: Validate raw JSON without instantiating objects (ideal for high-throughput APIs and PATCH requests).
4. **Standalone Values (`constraint.validate()`)**: Check individual variables directly.

> Dictionary and standalone validation are detailed in the [Advanced Usage](advanced.md) guide.

---

## The Dataclass Lifecycle

When applied to a class, `@monk` locks objects until they are proven valid. *(Function and dictionary validation bypass this and evaluate instantly).*

1. **Instantiation**: Object creation is instant, but attribute access is blocked.
2. **Validation**: Explicitly call `validate()` to evaluate the data against your rules.
3. **Safe Access**: Once validated, the object unlocks and behaves exactly like a standard Python dataclass.

```python
from monk import validate

# 1. Instantiation (Deferred)
user = User(email="bad-email", age=12)
# user.email  <-- ❌ Raises UnvalidatedAccessError

# 2. Validation
try:
    valid_user = validate(user)
    
    # 3. Safe Access
    print(valid_user.email)
except ValidationError as e:
    print(e.errors) 
```

> 💡 Tip: Prefer objects to crash instantly on bad data? See [Fail-Fast](core_concepts.md#fail-fast-mode) Mode.

## Handling Errors

When validation fails, `iron-monk` raises a `ValidationError` containing all accumulated errors. Choose the format that fits your use case:

1. **Structured Data (`e.errors`)**: A `list` of dictionaries containing the `field`, `message`, and `code`.
2. **RFC 7807 (`e.to_rfc7807()`)**: A standard RFC 7807 Problem Details JSON dictionary. Perfect for REST APIs.
3. **Flattened Strings (`e.flatten()`)**: A `list` of `{field}: {message}` strings for logging or CLI outputs.

```python
from typing import Annotated

from monk import monk, validate
from monk.constraints import Email, Interval
from monk.exceptions import ValidationError

@monk
class User:
    email: Annotated[str, Email]
    age: Annotated[int, Interval(ge=18)]

try: 
    validate(User(email="bad-email", age=12))
except ValidationError as e: 
    # 1. Structured Data
    print(e.errors[0]["field"])   # "email"
    print(e.errors[0]["message"]) # "Must be a valid email address."
    
    # 2. RFC 7807 
    print(e.to_rfc7807(instance="/api/users"))
    # {"type": "about:blank", "status": 400, "instance": "/api/users", "errors": [...]}
    
    # 3. Flattened Strings
    print(e.flatten())
    # ["email: Must be a valid email address.", "age: Must be greater than or equal to 18."]
```

## Required vs. Optional Fields

Validation is driven explicitly by constraints, not type hints.

Fields with constraints are required by default. Passing `None` fails instantly with a `NotNull` error. Use the `Nullable` marker to explicitly allow `None`.

```python
from typing import Annotated
from monk import monk
from monk.constraints import Email, Each, Nullable, Len

@monk
class Profile:
    # 1. Strictly Required (None fails with NotNull)
    email: Annotated[str, Email]
    
    # 2. Top-Level Optional (None is safe)
    nickname: Annotated[str | None, Nullable, Len(max_len=10)] = None

    # 3. Nested Optional (List items can be None)
    tags: Annotated[list[str | None], Each(Nullable, Len(max_len=5))]
```

### Customizing the "Required" Error
Explicitly include the `NotNull` constraint to override the default missing-value error message or code.

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

### Optional Types (Aliases)
To reduce `str | None` and `Nullable` boilerplate when dealing with large, optional-heavy payloads (like `PATCH` endpoints), `iron-monk` provides built-in type aliases for common primitives.

```python
from typing import Annotated
from monk import monk
from monk.constraints import Len, OptStr, OptInt

@monk
class UpdatePayload:
    age: OptInt = None
    
    # You can safely stack extra constraints on top of the aliases
    username: Annotated[OptStr, Len(min_len=3)] = None
```
> **💡 Tip:** You aren't limited to the built-in aliases! Because `iron-monk` relies entirely on standard Python `typing`, you can create your own custom aliases for complex or parameterized types (like lists or dictionaries) to keep your codebase DRY.


### Global Nullability (For Type Checkers)

To let runtime type checkers (like `beartype`) handle required fields, configure `iron-monk` to allow `None` by default.
This safely skips constraints on missing data. You can still use `NotNull` for one-off exceptions.

**Via Environment Variable:**
```sh
export MONK_DEFAULT_ALLOW_NONE=true
```

**Via Code:**
```python
from monk import settings
settings.default_allow_none = True
```

## Fail-Fast Mode
`iron-monk` defers validation by default. To crash instantly on invalid data during instantiation, disable deferred validation.

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

## Function and Method Validation

The `@monk` decorator instantly validates function arguments and return values. (Unlike dataclasses, function validation does not defer; invalid arguments raise an error before the function executes).

### Validating Inputs & Outputs

Annotate parameters to guard inputs, and annotate the return type to prevent bad data from escaping (caught under the `return` field).

```python
from typing import Annotated
from monk import monk
from monk.constraints import Email, Interval, LowerCase

@monk
def process_user(
    email: Annotated[str, Email], 
    age: Annotated[int, Interval(ge=18)]
) -> Annotated[str, LowerCase]:
    return email.upper() # ❌ Bug: Returns uppercase

# 1. Bad Inputs
# process_user(email="bad", age=12) 
# ❌ ValidationError: ['email: Must be a valid email address.', 'age: Must be greater than or equal to 18.']

# 2. Bad Output
# process_user(email="test@domain.com", age=25)
# ❌ ValidationError: ['return: Failed validation for islower.']
```

### Async & Class Methods

`@monk` fully supports `async`, `@classmethod`, and `@staticmethod`. It must always be the innermost decorator.

```python
from typing import Annotated
from monk import monk
from monk.constraints import Each, IPAddress, Email

class NotificationService:
    @classmethod
    @monk
    def broadcast(cls, emails: Annotated[list[str], Each(Email)]):
        pass
        
    @staticmethod
    @monk
    async def ping(ip: Annotated[str, IPAddress]):
        pass
```