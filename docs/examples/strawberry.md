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

# 1. Create a composite decorator to keep models clean
def monk_input(cls=None, **kwargs):
    def wrap(c):
        return strawberry.input(monk(c), **kwargs)
    return wrap(cls) if cls is not None else wrap

# 2. Define the input
@monk_input
class AddressInput:
    zip_code: Annotated[str, Len(min_len=5, max_len=5)]
    routing_matrix: Annotated[list[list[str]], Unique, Each(Each(Len(min_len=3)))]


@monk_input
class RegisterUserInput:
    email: Annotated[str, Email]
    password: Annotated[str, Len(min_len=8)]
    address: AddressInput

# 3. Define structured Error and Success types (Errors as Data)
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
    errors: list[FieldError] | None = None

    @classmethod
    def from_validation_error(cls, e: ValidationError) -> Self:
        return cls(
            message="Input validation failed.",
            errors=[FieldError(field=to_camel_case(err["field"]), message=err["message"]) for err in e.errors],
        )

@strawberry.type
class Mutation:
    @strawberry.mutation
    def register_user(self, input: RegisterUserInput) -> RegisterSuccess | BadRequest:
        try:
            valid_input = validate(input)
        except ValidationError as e:
            return BadRequest.from_validation_error(e)

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
            password: "123",
            address: {
                zipCode: "12",
                routingMatrix: [["NW", "South"], ["NW", "South"]]
            }
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
        },
        {
          "field": "address.zipCode",
          "message": "Must have a minimum length of 5."
        },
        {
          "field": "address.routingMatrix",
          "message": "All elements must be unique."
        },
        {
          "field": "address.routingMatrix[0][0]",
          "message": "Must have a minimum length of 3."
        },
        {
          "field": "address.routingMatrix[1][0]",
          "message": "Must have a minimum length of 3."
        }
      ]
    }
  }
}
```
## 2. Fail-Fast Validation (Context & Headers)

When dealing with authentication headers or IP whitelisting, you *want* the request to crash instantly before the GraphQL engine wastes CPU cycles. Using `deferred_validation=False` turns `iron-monk` into an impenetrable bouncer.

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

# Simulated ASGI/WSGI Context Builder (e.g., FastAPI, Starlette, Flask)
def get_context(request_headers: dict, client_ip: str) -> AppContext:
    """
    If the headers are bad, the AppContext instantiation will instantly
    throw a ValidationError, rejecting the HTTP request early!
    """
    return AppContext(
        authorization=request_headers.get("Authorization", ""), 
        client_ip=client_ip
    )

# Invalid Request Example:
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
