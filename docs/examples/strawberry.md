# Strawberry GraphQL

`iron-monk` is the perfect companion for Strawberry GraphQL. It natively solves the "GraphQL Error" problem by allowing you to safely parse inputs and return strictly-typed GraphQL Union errors ("Errors as Data").

It is also a fantastic tool for explicitly securing your API boundaries via Context validation.

## 1. Deferred Validation (Inputs & Mutations)

Because `iron-monk` defers validation, Strawberry can safely instantiate your input object without crashing the GraphQL engine. You then explicitly validate it inside your resolver and map the errors to your schema!

```python
import strawberry
from typing import Annotated, Self
from strawberry.utils.str_converters import to_camel_case

from monk import monk, validate
from monk.constraints import Email, Len
from monk.exceptions import ValidationError

# 1. Define the input
@strawberry.input
@monk
class RegisterUserInput:
    email: Annotated[str, Email]
    password: Annotated[str, Len(min_len=8)]

# 2. Define structured Error and Success types (Errors as Data)
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

@strawberry.type
class Mutation:

    @strawberry.mutation
    def register_user(
        self,
        input: RegisterUserInput,
    ) -> RegisterSuccess | BadRequest:
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

schema = strawberry.Schema(mutation=Mutation)
```

### Output
#### Request
```graphql
mutation {
    registerUser(
        input: {
            email: "bad-email",
            password: "123"
        }
    ) {
        __typename
        ... on RegisterSuccess {
            email
        }
        ... on BadRequest {
            message
            errors {
                field
                message
            }
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
        {
          "field": "email",
          "message": "Must be a valid email address."
        },
        {
          "field": "password",
          "message": "Must have a minimum length of 8."
        }
      ]
    }
  }
}
```
## 2. Fail-Fast Validation (Context & Headers)

When dealing with authentication headers or IP whitelisting, you *want* the request to crash instantly before the GraphQL engine wastes CPU cycles. Using `deferred_validation=False` you can achieve this with `iron-monk`.

```python
import strawberry
from typing import Annotated
from monk import monk
from monk.constraints import StartsWith, IPAddress
from monk.exceptions import ValidationError

@monk(deferred_validation=False)
class AppContext:
    authorization: Annotated[str, StartsWith("Bearer ")]
    client_ip: Annotated[str, IPAddress]

@strawberry.type
class Query:
    @strawberry.field
    def secure_data(self, info: strawberry.Info) -> str:
        # Guaranteed 100% safe by the time it reaches the resolver
        context: AppContext = info.context
        return f"Secret data accessed securely by IP: {context.client_ip}"

schema = strawberry.Schema(query=Query)

def get_context(request_headers: dict, client_ip: str) -> AppContext:
    """If the headers are bad, we throw a ValidationError"""
    return AppContext(
        authorization=request_headers.get("Authorization", ""), 
        client_ip=client_ip
    )

try:
    get_context({"Authorization": "Basic token"}, "192.168.1.100")
except ValidationError as e:
    print("Request rejected!")
    for err in e.errors:
        print(f" - {err['field']}: {err['message']}")
```

### Output

```bash
Request rejected!
 - authorization: Must start with 'Bearer '
```
