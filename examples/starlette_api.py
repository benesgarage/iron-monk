import functools
from typing import Annotated
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.requests import Request
import uvicorn

from monk import monk, validate
from monk.constraints import Email, Len
from monk.exceptions import ValidationError


# 1. Define your payload schema
@monk
class CreateUserRequest:
    username: Annotated[str, Len(min_len=3, max_len=50)]
    email: Annotated[str, Email]


def validate_body(schema_cls):
    """A bridge decorator that wires Starlette and iron-monk together."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            try:
                payload = await request.json()
                user_input = schema_cls(**payload)
                valid_data = validate(user_input)
            except ValidationError as e:
                return JSONResponse({"detail": "Validation Failed", "errors": e.errors}, status_code=400)
            except Exception:
                return JSONResponse({"detail": "Invalid JSON payload"}, status_code=400)

            # Inject the validated object into the user's handler
            return await func(request, valid_data, *args, **kwargs)

        return wrapper

    return decorator


# 3. Your completely boilerplate-free HTTP handler!
@validate_body(CreateUserRequest)
async def create_user(request: Request, body: CreateUserRequest) -> JSONResponse:
    return JSONResponse({"message": f"User {body.username} created successfully!"}, status_code=201)


app = Starlette(debug=True, routes=[Route("/users", create_user, methods=["POST"])])

if __name__ == "__main__":
    print("🚀 Starting Starlette server on http://localhost:8000")
    print(
        """💡 Test it with: curl -X POST http://localhost:8000/users -H 'Content-Type: application/json' -d '{"username": "ab", "email": "bad"}'"""
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)
