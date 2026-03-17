import strawberry
from typing import Annotated, Self

from strawberry.utils.str_converters import to_camel_case
from monk import monk, validate
from monk.constraints import Email, Len, Unique, Each
from monk.exceptions import ValidationError


# 1. Optionally, create a composite decorator
def monk_input(cls=None, **kwargs):
    """Combines @monk and @strawberry.input into a single decorator."""

    def wrap(c):
        return strawberry.input(monk(c), **kwargs)

    return wrap(cls) if cls is not None else wrap


# 2. Define nested inputs to showcase iron-monk's deep recursion!
@monk_input
class AddressInput:
    zip_code: Annotated[str, Len(min_len=5, max_len=5)]
    routing_matrix: Annotated[list[list[str]], Unique, Each(Each(Len(min_len=3)))]


@monk_input
class RegisterUserInput:
    email: Annotated[str, Email]
    password: Annotated[str, Len(min_len=8)]
    address: AddressInput


# 3. Define structured Error and Success types (Union-based error handling)
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


@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "world"


schema = strawberry.Schema(query=Query, mutation=Mutation)


if __name__ == "__main__":
    bad_query = """
        mutation {
            registerUser(input: {
                email: "not-an-email", 
                password: "123",
                address: { zipCode: "12", routingMatrix: [["NW", "South"], ["NW", "South"]] }
            }) {
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
    """
    result = schema.execute_sync(bad_query)
    print("GraphQL Response:", result.data)

    # Output:
    # {
    #     "registerUser": {
    #         "__typename": "BadRequest",
    #         "message": "Input validation failed.",
    #         "errors": [
    #             {
    #                 "field": "email",
    #                 "message": "Must be a valid email address."
    #             },
    # ...
