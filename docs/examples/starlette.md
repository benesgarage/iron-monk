# Starlette (ASGI)

> https://github.com/Kludex/starlette

Starlette requires explicit payload handling. Pair `iron-monk` with Starlette's global exception handlers for automated RFC 7807 error responses. Then, validate incoming requests using high-throughput dictionaries or clean DTO decorators.

## The Integration
```python
import functools
from typing import Annotated, TypedDict
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.requests import Request

from monk import monk, validate, validate_dict
from monk.constraints import Email, Len
from monk.exceptions import ValidationError

# Global Exception Handler (Formats all validation errors as RFC 7807)
async def monk_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(exc.to_rfc7807(instance=request.url.path), status_code=400)

# --- Approach A: High-Throughput Dicts ---

class UserDict(TypedDict):
    username: Annotated[str, Len(min_len=3)]
    email: Annotated[str, Email]

async def create_user_dict(request: Request):
    # Validates and sanitizes instantly. Failures are caught by the global handler
    safe_data = validate_dict(await request.json(), UserDict, drop_extra_keys=True) 
    return JSONResponse(safe_data, status_code=201)

# --- Approach B: The DTO Bridge Decorator ---

def validate_body(schema_cls):
    """Injects validated DTOs into your handlers."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            valid_data = validate(schema_cls(**await request.json()))
            return await func(request, valid_data, *args, **kwargs)
        return wrapper
    return decorator

@monk
class CreateUserRequest:
    username: Annotated[str, Len(min_len=3)]
    email: Annotated[str, Email]

@validate_body(CreateUserRequest)
async def create_user_dto(request: Request, body: CreateUserRequest):
    return JSONResponse({"username": body.username, "email": body.email}, status_code=201)

# --- Register App ---

app = Starlette(
    routes=[
        Route("/users/dict", create_user_dict, methods=["POST"]),
        Route("/users/dto", create_user_dto, methods=["POST"])
    ],
    exception_handlers={ValidationError: monk_exception_handler}
)
```

### Output
```bash
$ curl -X POST http://localhost:8000/users/dict \
  -H 'Content-Type: application/json' \
  -d '{"username": "ab", "email": "bad"}'

# Formatted RFC 7807 Problem Details
{
  "type": "about:blank",
  "title": "Validation Error",
  "status": 400,
  "detail": "The provided data is invalid. See 'errors' for specific details.",
  "errors": [
    {
      "field": "username",
      "message": "Must have a minimum length of 3.",
      "code": "Len"
    },
    {
      "field": "email",
      "message": "Must be a valid email address.",
      "code": "Email"
    }
  ],
  "instance": "/users/dict"
}
```
