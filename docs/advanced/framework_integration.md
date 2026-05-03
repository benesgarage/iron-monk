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

## Type metadata

When integrating `iron-monk` with complex frameworks like Strawberry GraphQL, SQLAlchemy, or custom internal tooling, you may encounter custom generic wrappers (e.g., `Maybe[T]`, `Mapped[T]`). 
You can configure `iron-monk` globally to tie constraints to these types when detected.

```python
import strawberry
from monk import settings
from monk.constraints import Nullable

# Type Metadata (Compile-Time Schema)
# Teach iron-monk to inject specific constraints whenever it encounters a custom type hint.
# E.g., Map Strawberry's `Maybe` to `[Nullable]` so the schema knows it's optional.
settings.type_metadata = {strawberry.Maybe: [Nullable]}
```