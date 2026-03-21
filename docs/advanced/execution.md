# Dicts, Streams, & Execution

## Raw Dictionary Validation

While dataclasses are ergonomic, instantiating objects takes memory and time. If you are building high-throughput data pipelines or WebSocket servers, you might want to skip object creation entirely.

`iron-monk` allows you to validate Python dictionaries directly against a Python class using the `validate_dict` function. This skips the object allocation phase entirely, offering near-native performance while retaining the full power of the constraint engine.

```python
from typing import Annotated

from monk import validate_dict
from monk.constraints import Email, Interval
from monk.exceptions import ValidationError

# 1. Define your schema
class UserDict:
    email: Annotated[str, Email]
    age: Annotated[int, Interval(ge=18)]
    
# 2. Receive a raw dictionary from your framework (e.g., json.loads)
raw_payload = {"email": "bad-email", "age": 12}

# 3. Validate it instantly without creating an object
try:
    safe_dict = validate_dict(raw_payload, UserDict)
except ValidationError as e:
    print(e.flatten())
    # ['email: Must be a valid email address.', 'age: Must be greater than or equal to 18.']
```

## Partial Validation (PATCH Requests)

When building HTTP `PATCH` endpoints, clients only send the fields they wish to update.

Because Python dataclasses cannot be instantiated with missing required arguments, developers often struggle to reuse their `POST` models for `PATCH` endpoints.
By passing `partial=True` to `validate_dict`, `iron-monk` will ignore any missing keys, but will validate the keys that are present against your schema.

### Handling Divergent Rules (Schema Composition)

Often, the rules for creating an object are different than updating it. For example, a user must provide an email on creation, but they are never allowed to update it later.

Because `validate_dict` doesn't require a special `TypedDict` and works with standard Python classes, you can use basic inheritance to keep your rules DRY while safely omitting fields:

```python
from typing import Annotated
from monk import monk, validate_dict
from monk.constraints import Email, Interval, Len
from monk.exceptions import ValidationError

# 1. The Base (Shared rules)
class UserBase:
    age: Annotated[int, Interval(ge=18)]

# 2. The full Object (Decorated with @monk, becomes a full Dataclass)
@monk
class User(UserBase):
    email: Annotated[str, Email]             # Can only be set on creation
    username: Annotated[str, Len(min_len=10)] # Must be long on creation

# 3. The PATCH Schema (Standard class, inherits base rules)
class UserUpdate(UserBase):
    # Email is omitted entirely! If they try to patch it, it gets ignored.
    # Username has a relaxed rule for updates!
    username: Annotated[str, Len(min_len=5)]

# Example API Endpoint
async def patch_user(request):
    raw_json = await request.json() 
    
    try:
        # Validate the partial update against our PATCH schema
        safe_patch_data = validate_dict(raw_json, UserUpdate, partial=True)
    except ValidationError as e:
        return {"errors": e.errors}, 400
        
    # Hand the safe dictionary directly to your ORM
    # await db.users.update(**safe_patch_data)
    
    return {"updated": safe_patch_data}
```

> ⚡ The "Explicit Null" Guarantee: Python dataclasses struggle to differentiate between a field being explicitly set to `None` vs. being completely omitted. Because `validate_dict` checks the raw dictionary directly, we avoid this limitation. If a client sends `{"username": None}`, the `NotNull` constraint will still block it. It only ignores fields that are omitted from the dictionary.


## Direct Execution (Standalone Variables)

Sometimes you don't need a full Data Transfer Object, a function decorator, or a dictionary schema. You might just have a single variable in the middle of a script that you want to quickly verify.

Because `iron-monk` constraints are just standard Python classes, you can instantiate them and call `.validate(value)` directly. 

> **⚡ Note:** When executing constraints directly, they do **not** raise a `ValidationError` (since there is no object to aggregate multiple errors for). Instead, they raise standard Python `ValueError` or `TypeError` exceptions!

```python
from monk.constraints import Email, Interval

# 1. Success (Returns silently)
Email().validate("test@domain.com")

# 2. Failure (Raises ValueError)
Interval(ge=18).validate(12) 
# ValueError: Must be greater than or equal to 18.

# 3. Type Error (Raises TypeError)
Email().validate(123) 
# TypeError: Type 'int' cannot be validated as an email.
```

## Validating Generators and Streams

Constraints that need to inspect multiple items in a collection (like `Each`, `Contains`, and `Unique`) natively **reject exhaustible iterators** (streams) and will raise a `TypeError`.

If `iron-monk` were to silently evaluate a generator during validation, due to our eager validation, it would exhaust. By the time the validation finished, your application would be left with an empty iterator.

If we were to magically replace your argument with a lazy proxy generator, it would strip away the original type of any custom stream objects you passed (like a `WebSocket` or a `FileStream`), directly violating our **Zero Coercion** philosophy.

### Lazy Stream Validation
To safely validate infinite streams, massive files, or WebSockets without blowing up your memory by converting them to a list, `iron-monk` provides `validate_stream` and `validate_async_stream`.

These utilities act as explicit proxies. You wrap your generator right where you consume it, and it validates items one-by-one on the fly. If an invalid item pops out, it instantly raises a `ValidationError` before your application processes it.

```python
from typing import Iterator
from monk import validate_stream
from monk.constraints import Email, EndsWith

def process_data(stream: Iterator[str]):
    # Validate items lazily, passing multiple constraints as arguments
    safe_stream = validate_stream(stream, Email, EndsWith("@domain.com"))
    
    for item in safe_stream:
        print(f"Safe to process: {item}")

gen = (x for x in ["test@domain.com", "hacker@evil.com"])

process_data(gen)
# Output:
# Safe to process: test@domain.com
# ❌ raises ValidationError: ["[1]: Must end with '@domain.com'"]
```

> If you are working with async iterators (like streaming database records or ASGI receivers), simply use `validate_async_stream` instead!
 

## Deeply Nested Dictionaries

If your JSON payload is heavily nested, use the `Nested` constraint. This acts as a bridge, allowing the engine to recursively validate complex JSON architectures without instantiating any objects.

```python
from typing import TypedDict, Annotated
from monk import validate_dict
from monk.constraints import Email, Len, Each, Nested

class AddressDict(TypedDict):
    city: Annotated[str, Len(min_len=2)]

class UserDict(TypedDict):
    email: Annotated[str, Email]
    # Use the nested schema as the base type for perfect MyPy/IDE autocomplete!
    address: Annotated[AddressDict, Nested(AddressDict)]
    history: Annotated[list[AddressDict], Each(Nested(AddressDict))]
    
payload = {
    "email": "bad",
    "address": {"city": "A"},
    "history": [{"city": "B"}]
}

validate_dict(payload, UserDict)
# ❌ raises: ['email: Must be a valid email address.', 'address.city: Must have a minimum length of 2.', 'history[0].city: Must have a minimum length of 2.']
```
