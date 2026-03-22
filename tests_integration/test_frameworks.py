import pytest
from typing import Annotated, TypedDict
from monk import monk, validate, validate_dict
from monk.constraints import Email, Len, Interval, Each
from monk.exceptions import ValidationError


# ---------------------------------------------------------
# 1. Beartype Integration
# ---------------------------------------------------------
def test_beartype_integration() -> None:
    from beartype import beartype
    from beartype.roar import BeartypeCallHintParamViolation

    @beartype
    @monk
    class BeartypeUser:
        email: Annotated[str, Email]
        age: Annotated[int, Interval(ge=18)]

    # Type Checking (Caught by beartype)
    with pytest.raises(BeartypeCallHintParamViolation):
        BeartypeUser(email="test@domain.com", age="twenty")  # type: ignore

    # Value Validation (Caught by iron-monk)
    with pytest.raises(ValidationError) as exc:
        validate(BeartypeUser(email="bad-email", age=12))

    assert len(exc.value.errors) == 2


# ---------------------------------------------------------
# 2. Tyro Integration
# ---------------------------------------------------------
def test_tyro_integration() -> None:
    import tyro

    @monk
    class CLIArgs:
        tags: Annotated[list[str], Each(Len(min_len=3))]
        max_warnings: Annotated[int, Interval(ge=0)] = 10

    # Success path
    args = tyro.cli(CLIArgs, args=["--tags", "abc", "def", "--max-warnings", "5"])
    valid_args = validate(args)
    assert valid_args.max_warnings == 5
    assert valid_args.tags == ["abc", "def"]

    # Failure path
    bad_args = tyro.cli(CLIArgs, args=["--tags", "a", "def"])
    with pytest.raises(ValidationError) as exc:
        validate(bad_args)

    assert exc.value.errors[0]["field"] == "tags[0]"


# ---------------------------------------------------------
# 3. Starlette Integration
# ---------------------------------------------------------
def test_starlette_integration() -> None:
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from starlette.requests import Request
    from starlette.testclient import TestClient

    async def monk_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(exc.to_rfc7807(instance=request.url.path), status_code=400)

    class UserDict(TypedDict):
        username: Annotated[str, Len(min_len=3)]

    async def create_user_dict(request: Request) -> JSONResponse:
        payload = await request.json()
        safe_data = validate_dict(payload, UserDict, drop_extra_keys=True)
        return JSONResponse(safe_data, status_code=201)

    app = Starlette(
        routes=[Route("/users/dict", create_user_dict, methods=["POST"])],
        exception_handlers={ValidationError: monk_exception_handler},  # type: ignore
    )
    client = TestClient(app)

    # Success (Drops extra keys)
    resp1 = client.post("/users/dict", json={"username": "kai", "is_admin": True})
    assert resp1.status_code == 201
    assert resp1.json() == {"username": "kai"}

    # Failure (Returns RFC 7807)
    resp2 = client.post("/users/dict", json={"username": "a"})
    assert resp2.status_code == 400
    assert resp2.json()["type"] == "about:blank"
    assert resp2.json()["errors"][0]["field"] == "username"


# ---------------------------------------------------------
# 4. Strawberry GraphQL Integration
# ---------------------------------------------------------
def test_strawberry_integration() -> None:
    import strawberry

    @strawberry.input
    @monk
    class RegisterInput:
        email: Annotated[str, Email]

    @strawberry.type
    class Query:
        @strawberry.field
        def check_email(self, input: RegisterInput) -> str:
            valid = validate(input)
            return valid.email

    schema = strawberry.Schema(query=Query)

    # Validation Deferred (Parsed correctly by Strawberry)
    res1 = schema.execute_sync('query { checkEmail(input: {email: "test@domain.com"}) }')
    assert res1.errors is None
    assert res1.data == {"checkEmail": "test@domain.com"}

    # Validation Fails explicitly in resolver
    res2 = schema.execute_sync('query { checkEmail(input: {email: "bad"}) }')
    assert res2.errors is not None
    assert "Validation failed" in str(res2.errors[0].original_error)


# ---------------------------------------------------------
# 5. SQLAlchemy 2.0 Integration (DTO Pattern)
# ---------------------------------------------------------
def test_sqlalchemy_dto_integration() -> None:
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

    class Base(DeclarativeBase):
        pass

    class UserDB(Base):
        __tablename__ = "users"
        id: Mapped[int] = mapped_column(primary_key=True)
        username: Mapped[str]

    @monk
    class CreateUserDTO:
        username: Annotated[str, Len(min_len=3)]

    # Ensure DTO accurately represents DB inputs safely
    with pytest.raises(ValidationError):
        validate(CreateUserDTO(username="ab"))

    dto = validate(CreateUserDTO(username="kai"))
    user = UserDB(username=dto.username)
    assert user.username == "kai"


# ---------------------------------------------------------
# 6. Tortoise ORM Integration (DTO Pattern)
# ---------------------------------------------------------
def test_tortoise_orm_integration() -> None:
    import dataclasses
    from tortoise.models import Model
    from tortoise import fields

    class UserDB(Model):
        id = fields.IntField(primary_key=True)
        username = fields.CharField(max_length=50, unique=True)
        email = fields.CharField(max_length=255, unique=True)

        class Meta:
            table = "users"

    @monk
    class CreateUserDTO:
        username: Annotated[str, Len(min_len=3, max_len=50)]
        email: Annotated[str, Email]

    # Ensure DTO accurately represents DB inputs safely
    with pytest.raises(ValidationError):
        validate(CreateUserDTO(username="ab", email="bad-email"))

    dto = validate(CreateUserDTO(username="kai", email="test@domain.com"))
    user = UserDB(**dataclasses.asdict(dto))

    assert user.username == "kai"
    assert user.email == "test@domain.com"
