# Framework Integration: Unwrappers & Sentinels

When integrating `iron-monk` with external frameworks (like GraphQL libraries, ORMs, or web frameworks), you may encounter custom wrapper objects or missing-value sentinels. 

`iron-monk` provides global settings to handle these natively without coercing or mutating your underlying data.

## Safely Unwrapping Values

Some frameworks wrap provided values in an object (e.g., a `Some` or `Optional` monad). Because `iron-monk` evaluates strict types, a constraint like `Email` will fail if it receives a wrapper object instead of a string.

You can teach `iron-monk` how to globally extract the inner value for validation using `settings.unwrappers`. The engine will evaluate the extracted value, but the original wrapper object remains completely untouched.

```python
from typing import Annotated, TypeVar, Generic
from monk import monk, validate, settings
from monk.constraints import Email

T = TypeVar("T")

# A mock framework wrapper
class SomeWrapper(Generic[T]):
    def __init__(self, value: T):
        self.value = value

# 1. Teach iron-monk how to extract the inner value
settings.unwrappers = {
    SomeWrapper: lambda x: x.value
}

@monk
class UpdateRequest:
    email: SomeWrapper[Annotated[str, Email]]

# 2. Safely evaluates the inner string, but preserves the original wrapper!
req = validate(UpdateRequest(email=SomeWrapper("test@domain.com")))

assert isinstance(req.email, SomeWrapper)
assert req.email.value == "test@domain.com"
```

## Ignoring Sentinels (PATCH Endpoints)

When building `PATCH` updates, frameworks often use a singleton sentinel object (like `UNSET` or `Undefined`) to differentiate between a field explicitly set to `None` versus a field that was completely omitted by the client.

You can use `settings.ignored_sentinels` to tell `iron-monk` to instantly skip validation if it encounters one of these singletons.

```python
from typing import Annotated
from monk import monk, validate, settings
from monk.constraints import Email

# A mock framework singleton sentinel
class UnsetType:
    pass

UNSET = UnsetType()

# 1. Tell iron-monk to skip validation for this exact instance
settings.ignored_sentinels = (UNSET,)

@monk
class PatchRequest:
    email: UnsetType | Annotated[str, Email] = UNSET

# 2. Validation is safely skipped because the value is UNSET!
req = validate(PatchRequest())

assert req.email is UNSET
```