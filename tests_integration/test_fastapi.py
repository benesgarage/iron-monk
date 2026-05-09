import pytest
from typing import Annotated, TypeVar, Type
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.testclient import TestClient
from pydantic_core import core_schema

from monk import monk, validate
from monk.constraints import Email, Len
from monk.exceptions import ValidationError

# ==============================================================================
# 1. Integration Tools (What we discussed previously)
# ==============================================================================

T = TypeVar("T")


def MonkBody(schema_cls: Type[T]):
    """Approach 1: FastAPI dependency bridge for iron-monk validation."""

    async def _extract_and_validate(request: Request) -> T:
        body = await request.json()
        try:
            return validate(schema_cls(**body))
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.to_rfc7807(status=422, instance=request.url.path))

    return Depends(_extract_and_validate)


def fastapi_monk(cls):
    """Approach 2: Duck-typing decorator targeting Pydantic Core."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        def validate_via_monk(value: dict, info) -> cls:
            try:
                return validate(cls(**value))
            except ValidationError as e:
                raise ValueError("\n".join(e.flatten()))

        return core_schema.with_info_plain_validator_function(validate_via_monk)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        return {"type": "object", "properties": {}}

    cls.__get_pydantic_core_schema__ = __get_pydantic_core_schema__
    cls.__get_pydantic_json_schema__ = __get_pydantic_json_schema__
    return cls


# ==============================================================================
# 2. App & Route Setup
# ==============================================================================

app = FastAPI()


@monk
class UserDependsReq:
    username: Annotated[str, Len(min_len=3)]
    email: Annotated[str, Email]


@fastapi_monk
@monk
class UserDuckReq:
    username: Annotated[str, Len(min_len=3)]
    email: Annotated[str, Email]


@app.post("/users/depends")
async def create_user_depends(user: UserDependsReq = MonkBody(UserDependsReq)):
    return {"message": "success", "email": user.email}


@app.post("/users/duck")
async def create_user_duck(user: UserDuckReq):
    return {"message": "success", "email": user.email}


client = TestClient(app)

# ==============================================================================
# 3. The Tests
# ==============================================================================


@pytest.mark.parametrize("endpoint", ["/users/depends", "/users/duck"])
def test_fastapi_happy_path(endpoint):
    payload = {"username": "kai_benevento", "email": "kai@example.com"}
    response = client.post(endpoint, json=payload)

    assert response.status_code == 200
    assert response.json() == {"message": "success", "email": "kai@example.com"}


def test_fastapi_depends_aggregates_errors():
    payload = {"username": "ab", "email": "bad-email"}
    response = client.post("/users/depends", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]

    # Ensure RFC 7807 standard is maintained and both errors are caught!
    assert detail["status"] == 422
    assert len(detail["errors"]) == 2

    failed_fields = {e["field"] for e in detail["errors"]}
    assert "username" in failed_fields
    assert "email" in failed_fields


def test_fastapi_duck_typing_catches_errors():
    payload = {"username": "ab", "email": "bad-email"}
    response = client.post("/users/duck", json=payload)

    # Pydantic native catches it and raises a 422 Unprocessable Entity
    assert response.status_code == 422

    detail = response.json()["detail"]
    # The Pydantic wrapper wraps our ValueError containing the flattened string
    assert "Must have a minimum length of 3." in detail[0]["msg"]
    assert "Must be a valid email address." in detail[0]["msg"]
