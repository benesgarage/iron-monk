# Strawberry GraphQL

> https://github.com/strawberry-graphql/strawberry

`iron-monk` pairs natively with Strawberry GraphQL. It solves the "GraphQL Error" problem by allowing you to parse inputs and return strictly-typed Union errors ("Errors as Data"), while also securing your API boundaries via fail-fast Context validation.

## 1. Deferred Validation (Inputs)

Because `iron-monk` defers validation, Strawberry can safely instantiate input objects without crashing the GraphQL engine. You explicitly validate them inside your resolver and map the errors to your schema.

### Step 1: Define your Types
```python
import strawberry
from typing import Annotated
from monk import monk
from monk.constraints import Email, Len

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
```

### Step 2: The Resolver

```python
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
            return BadRequest(
                message="Input validation failed.",
                errors=[
                    FieldError(field=to_camel_case(err["field"]), message=err["message"])
                    for err in e.errors
                ],
            )

        return RegisterSuccess(email=valid_input.email)
```

### Output
#### Request
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

#### Response
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
## 2. Fail-Fast Validation (Context & Headers)

For authentication headers or IP whitelisting, you may want the request to crash before it reaches the resolver. Use defer=False to reject bad requests instantly during Context creation.

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
    # ❌ Fails instantly if headers or IP are invalid
    return AppContext(
        authorization=request_headers.get("Authorization", ""), 
        client_ip=client_ip
    )

@strawberry.type
class Query:
    @strawberry.field
    def secure_data(self, info: strawberry.Info) -> str:
        # ✅ Guaranteed 100% safe by the time it reaches the resolver
        context: AppContext = info.context
        return f"Secret data accessed securely by IP: {context.client_ip}"
```
