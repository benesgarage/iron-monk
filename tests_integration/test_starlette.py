from typing import Annotated, TypedDict
from monk import validate_dict
from monk.constraints import Len
from monk.exceptions import ValidationError


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

    resp1 = client.post("/users/dict", json={"username": "kai", "is_admin": True})
    assert resp1.status_code == 201
    assert resp1.json() == {"username": "kai"}

    resp2 = client.post("/users/dict", json={"username": "a"})
    assert resp2.status_code == 400
    assert resp2.json()["type"] == "about:blank"
