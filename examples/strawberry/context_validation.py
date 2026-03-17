import strawberry
from typing import Annotated

from monk import monk
from monk.constraints import StartsWith, IPAddress
from monk.exceptions import ValidationError


# 1. Define the strictly typed Context.
# By passing deferred_validation=False, we tell iron-monk to instantly
# crash upon instantiation if the data is bad. This is perfect for
# security barriers like HTTP headers and authentication.
@monk(deferred_validation=False)
class AppContext:
    authorization: Annotated[str, StartsWith("Bearer ")]
    client_ip: Annotated[str, IPAddress]


# 2. Strawberry GraphQL Setup
@strawberry.type
class Query:
    @strawberry.field
    def secure_data(self, info: strawberry.Info) -> str:
        # By the time Strawberry routes to this resolver, we are 100%
        # guaranteed that the context is valid and safe to use.
        context: AppContext = info.context
        return f"Secret data accessed securely by IP: {context.client_ip}"


schema = strawberry.Schema(query=Query)


# 3. Simulated ASGI/WSGI Context Builder (e.g., FastAPI, Starlette, Flask)
def get_context(request_headers: dict, client_ip: str) -> AppContext:
    """
    This function runs before the GraphQL engine executes the query.
    If the headers are bad, the AppContext instantiation will instantly
    throw a ValidationError, rejecting the HTTP request early
    """
    return AppContext(authorization=request_headers.get("Authorization", ""), client_ip=client_ip)


if __name__ == "__main__":
    # --- Test 1: Valid Request ---
    print("--- 🟢 Testing Valid Request ---")
    valid_headers = {"Authorization": "Bearer my-secret-token"}
    ip = "192.168.1.100"

    context = get_context(valid_headers, ip)
    result = schema.execute_sync("{ secureData }", context_value=context)
    print("GraphQL Response:", result.data)

    # --- Test 2: Invalid Request ---
    print("\n--- 🔴 Testing Invalid Request ---")
    bad_headers = {"Authorization": "Basic some-other-token"}  # Fails StartsWith

    try:
        get_context(bad_headers, ip)
    except ValidationError as e:
        print("Request rejected!")
        for err in e.errors:
            print(f" - {err['field']}: {err['message']}")
