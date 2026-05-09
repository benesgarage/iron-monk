# FastAPI

FastAPI's request lifecycle is built around Pydantic, but `iron-monk` slots in cleanly at the boundary. Two patterns work well: a `Depends`-based bridge that keeps your handlers Pydantic-free and explicit, or a duck-typing decorator that masquerades a `@monk` class as a Pydantic model so existing handler signatures keep working.

Project: <https://github.com/fastapi/fastapi>

## Approach A: `Depends` bridge

Inject validation through FastAPI's dependency system. The `Depends` callable parses the request body, instantiates the `@monk` class, calls `validate()`, and converts any `ValidationError` into an RFC 7807 `HTTPException`. Pydantic never sees the schema.

```python
from typing import Annotated, TypeVar, Type
from fastapi import FastAPI, Depends, Request, HTTPException

from monk import monk, validate
from monk.constraints import Email, Len
from monk.exceptions import ValidationError

T = TypeVar("T")

def MonkBody(schema_cls: Type[T]):
    """FastAPI dependency bridge for iron-monk validation."""
    async def _extract_and_validate(request: Request) -> T:
        body = await request.json()
        try:
            return validate(schema_cls(**body))
        except ValidationError as e:
            raise HTTPException(
                status_code=422,
                detail=e.to_rfc7807(status=422, instance=request.url.path),
            )
    return Depends(_extract_and_validate)

@monk
class CreateUserRequest:
    username: Annotated[str, Len(min_len=3)]
    email: Annotated[str, Email]

app = FastAPI()

@app.post("/users")
async def create_user(user: CreateUserRequest = MonkBody(CreateUserRequest)):
    return {"message": "success", "email": user.email}
```

A failed payload returns the full RFC 7807 problem-detail document under `detail`, with every field error aggregated:

```bash
$ curl -X POST http://localhost:8000/users \
  -H 'Content-Type: application/json' \
  -d '{"username": "ab", "email": "bad-email"}'

{
  "detail": {
    "type": "about:blank",
    "title": "Validation Error",
    "status": 422,
    "detail": "The provided data is invalid. See 'errors' for specific details.",
    "errors": [
      {"field": "username", "message": "Must have a minimum length of 3.", "code": "Len"},
      {"field": "email", "message": "Must be a valid email address.", "code": "Email"}
    ],
    "instance": "/users"
  }
}
```

## Approach B: Pydantic Core duck-typing

If you want the standard FastAPI signature (`async def handler(user: CreateUserRequest)`) without an explicit `Depends`, you can teach Pydantic Core to delegate validation to `iron-monk` by implementing two dunder hooks. FastAPI treats the class as a body model and routes parsed JSON through `validate_via_monk`.

```python
from typing import Annotated
from fastapi import FastAPI
from pydantic_core import core_schema

from monk import monk, validate
from monk.constraints import Email, Len
from monk.exceptions import ValidationError

def fastapi_monk(cls):
    """Duck-typing decorator targeting Pydantic Core."""
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

@fastapi_monk
@monk
class CreateUserRequest:
    username: Annotated[str, Len(min_len=3)]
    email: Annotated[str, Email]

app = FastAPI()

@app.post("/users")
async def create_user(user: CreateUserRequest):
    return {"message": "success", "email": user.email}
```

Pydantic wraps the raised `ValueError` into its own 422 response, so error messages arrive as a flattened newline-joined string under `detail[0].msg` rather than the structured RFC 7807 shape from Approach A.

## Choosing between them

| | Approach A (`MonkBody`) | Approach B (`fastapi_monk`) |
| --- | --- | --- |
| Handler signature | `user: T = MonkBody(T)` | `user: T` (idiomatic FastAPI) |
| Error format | RFC 7807 problem-detail | Pydantic's default 422 envelope |
| OpenAPI schema | Body type opaque to FastAPI | Empty object stub (customizable) |
| Pydantic dependency | None | Requires `pydantic_core` |

Pick **A** when you want clean error responses and don't mind the explicit dependency declaration. Pick **B** when you're migrating an existing Pydantic-shaped codebase and want `iron-monk` to take over validation without changing handler signatures.
