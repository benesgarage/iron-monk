# Strawberry GraphQL

Strawberry GraphQL is a natural fit for `iron-monk`. The deferred validation model lets Strawberry instantiate input objects without crashing the engine, and you can map the resulting `ValidationError` straight to a strictly-typed Union ("errors as data").

Project: <https://github.com/strawberry-graphql/strawberry>

## 1. Deferred validation (inputs)

Because `iron-monk` defers validation by default, Strawberry safely instantiates inputs without crashing. Validate them inside your resolver and map errors to your schema.

### Define your types
```python
from typing import Annotated, Self

import strawberry
from strawberry.utils.str_converters import to_camel_case
from monk import monk
from monk.constraints import Email, Len
from monk.exceptions import ValidationError

# 1. The Input (Decorated with @monk)
@strawberry.input
@monk
class RegisterUserInput:
    email: Annotated[str, Email]
    password: Annotated[str, Len(min_len=8)]

# 2. The Response Types (Errors as Data)
@strawberry.type
class RegisterSuccess:
    email: str

@strawberry.type
class FieldError:
    field: str
    message: str

@strawberry.type
class BadRequest:
    message: str
    errors: list[FieldError]

    @classmethod
    def from_exc(cls, e: ValidationError) -> Self:
        return cls(
            message="Input validation failed.",
            errors=[
                FieldError(field=to_camel_case(err["field"]), message=err["message"])
                for err in e.errors
            ]
        )
```

### The resolver

```python
import strawberry
from strawberry.utils.str_converters import to_camel_case
from monk import validate
from monk.exceptions import ValidationError

@strawberry.type
class Mutation:

    @strawberry.mutation
    def register_user(self, input: RegisterUserInput) -> RegisterSuccess | BadRequest:
        try:
            valid_input = validate(input)
        except ValidationError as e:
            return BadRequest.from_exc(e)

        return RegisterSuccess(email=valid_input.email)
```

### Output

**Request:**
```graphql
mutation {
    registerUser(input: { email: "bad", password: "123" }) {
        __typename
        ... on BadRequest {
            message
            errors { field message }
        }
    }
}
```

**Response:**
```json
{
  "data": {
    "registerUser": {
      "__typename": "BadRequest",
      "message": "Input validation failed.",
      "errors": [
        { "field": "email", "message": "Must be a valid email address." },
        { "field": "password", "message": "Must have a minimum length of 8." }
      ]
    }
  }
}
```
## 2. Fail-fast validation (context & headers)

For authentication headers or IP whitelisting, you want the request to fail before it ever reaches a resolver. Use `defer=False` so context creation rejects bad requests instantly.

```python
import strawberry
from typing import Annotated
from monk import monk
from monk.constraints import StartsWith, IPAddress

@monk(defer=False)
class AppContext:
    authorization: Annotated[str, StartsWith("Bearer ")]
    client_ip: Annotated[str, IPAddress]

def get_context(request_headers: dict, client_ip: str) -> AppContext:
    # Fails instantly if headers or IP are invalid
    return AppContext(
        authorization=request_headers.get("Authorization", ""),
        client_ip=client_ip,
    )

@strawberry.type
class Query:
    @strawberry.field
    def secure_data(self, info: strawberry.Info) -> str:
        # By the time we get here, context is fully validated.
        context: AppContext = info.context
        return f"Secret data accessed by IP: {context.client_ip}"
```

## 3. Custom GraphQL scalars

GraphQL ships with a small handful of built-in scalars (`Int`, `String`, etc.). To add `HexColor` or `Cron` to your schema, you usually write a custom scalar with parse logic.

`iron-monk` constraints are standalone callables, so they drop into Strawberry's `parse_value` hook directly:

```python
import strawberry
from strawberry.schema.config import StrawberryConfig
from typing import NewType
from monk.constraints import HexColor, Cron

# 1. Create native Python NewTypes
HexColorType = NewType("HexColorType", str)
AWSCronType = NewType("AWSCronType", str)

# 2. Use iron-monk constraints directly in the parse hook!
def parse_hex(value: str) -> HexColorType:
    HexColor().validate(value) # Raises ValueError on bad data
    return HexColorType(value)

def parse_cron(value: str) -> AWSCronType:
    Cron(allow_aws=True).validate(value)
    return AWSCronType(value)

# 3. Use the NewTypes directly in your schema!
@strawberry.type
class ProfileTheme:
    primary_color: HexColorType
    email_schedule: AWSCronType

@strawberry.type
class Query:
    theme: ProfileTheme

# 4. Map the scalars when building the schema
schema = strawberry.Schema(
    query=Query,
    config=StrawberryConfig(
        scalar_map={
            HexColorType: strawberry.scalar(name="HexColor", parse_value=parse_hex),
            AWSCronType: strawberry.scalar(name="AWSCron", parse_value=parse_cron),
        }
    )
)
```

## 4. Defensive egress wrappers

GraphQL APIs often front legacy databases or third-party REST APIs. If the upstream returns `"website": "not-a-url"`, Strawberry will happily serve that to your frontend and break the UI.

Use `validate_dict(..., drop_extra_keys=True)` inside the resolver to sanitize external data *before* it reaches the GraphQL engine:

```python
import strawberry
from typing import TypedDict, Annotated
from monk import validate_dict
from monk.constraints import URL, Email

# 1. Define the shape of the external REST API payload
class LegacyUserDict(TypedDict):
    email: Annotated[str, Email]
    website: Annotated[str, URL]

@strawberry.type
class User:
    email: str
    website: str

@strawberry.type
class Query:
    @strawberry.field
    def fetch_legacy_user(self) -> User:
        # Imagine this came from requests.get("http://legacy-api.internal/user/1")
        raw_payload = {
            "email": "john@domain.com", 
            "website": "https://example.com", 
            "internal_db_id": 99281, # We don't want to leak this!
            "is_admin": True
        }
        
        # 2. Validate and sanitize 
        # Strips out 'internal_db_id' and 'is_admin', and ensures the URL/Email are valid
        safe_data = validate_dict(raw_payload, LegacyUserDict, drop_extra_keys=True)
        
        # 3. Hand clean, mathematically proven data to Strawberry
        return User(**safe_data)
```

## 5. Resolver argument validation

Queries often take arguments like `limit`, `offset`, or `search`. Validating that `limit` is between 1 and 100 usually means boilerplate `if limit < 1: raise Exception(...)` inside every resolver.

`@monk` decorates regular Python functions, so it stacks directly on top of Strawberry resolvers.

!!! note
    This is fail-fast validation. If you prefer errors-as-data, route arguments through an input object and validate that inside the resolver.

```python
import strawberry
from typing import Annotated
from monk import monk
from monk.constraints import Interval, Trimmed

@strawberry.type
class Query:
    @strawberry.field
    @monk
    def search_products(
        self, 
        # Validate arguments before the resolver body executes
        limit: Annotated[int, Interval(gt=0, le=100)] = 20,
        offset: Annotated[int, Interval(ge=0)] = 0,
    ) -> list[str]:
        
        # The logic here is 100% safe. Limit is guaranteed to be 1-100.
        db_results = ["apple", "banana", "cherry", "date"]
        return db_results[offset : offset + limit]
```

## 6. Unwrapping Strawberry's `Maybe`

When building `PATCH` mutations, Strawberry wraps provided values in a `Some` object. Teach `iron-monk` how to extract the inner value for validation, while leaving the wrapper itself untouched on the model. See **[Settings & Type Metadata](../advanced/settings.md)** for the broader pattern.

```python
import strawberry
from strawberry.types import Some
from typing import Annotated
from monk import monk, validate, settings
from monk.constraints import Email

# Teach iron-monk how to extract the value
settings.unwrappers = {Some: lambda x: x.value}

@strawberry.input
@monk
class UpdateUserInput:
    email: strawberry.Maybe[Annotated[str, Email]]

@strawberry.type
class Mutation:
    @strawberry.mutation
    def patch_user(self, input: UpdateUserInput) -> str:
        valid = validate(input)
        
        if valid.email is None:
            return "Email omitted."
        
        return f"Updated email: {valid.email.value}"
```
