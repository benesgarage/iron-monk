# Starlette (ASGI)

Starlette is an ASGI web framework. Unlike heavy frameworks that force you into their specific dependency injection magic, Starlette expects you to handle request payloads explicitly. 

Because of this, `iron-monk` works well with Starlette. By writing a simple "Bridge Decorator", you can achieve the boilerplate-free Developer Experience of FastAPI while retaining absolute, explicit control over your HTTP lifecycle.

```python
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

# 1. Build the Bridge Decorator
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

            # Inject the validated object directly into the user's handler
            return await func(request, valid_data, *args, **kwargs)
        return wrapper
    return decorator

# 2. Define your payload schema
@monk
class CreateUserRequest:
    username: Annotated[str, Len(min_len=3, max_len=50)]
    email: Annotated[str, Email]



# 3. Apply to your request handler
@validate_body(CreateUserRequest)
async def create_user(request: Request, body: CreateUserRequest) -> JSONResponse:
    return JSONResponse({"message": f"User {body.username} created successfully!"}, status_code=201)

app = Starlette(debug=True, routes=[Route("/users", create_user, methods=["POST"])])
```

### Output
```bash
$ curl -X POST http://localhost:8000/users 
-H 'Content-Type: application/json' 
-d '{"username": "ab", "email": "bad"}'
{ "detail": "Validation Failed", "errors": [ { "field": "username", "message": "Must have a minimum length of 3.", "constraint": "Len" }, { "field": "email", "message": "Must be a valid email address.", "constraint": "Email" } ] }
```
