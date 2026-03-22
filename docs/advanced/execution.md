# Dicts, Streams, & Execution

## Raw Dictionary Validation

Validate raw dictionaries directly against a schema using `validate_dict`. This skips object allocation for maximum performance.

```python
from typing import Annotated
from monk import validate_dict
from monk.constraints import Email, Interval

class UserDict:
    email: Annotated[str, Email]
    age: Annotated[int, Interval(ge=18)]
    
# Validate instantly without creating an object
safe_dict = validate_dict({"email": "test@domain.com", "age": 25}, UserDict)
```

### Strict Mode & Sanitization
`validate_dict` is strict by default. Unrecognized keys instantly raise a `ValidationError`.
To securely sanitize dirty payloads, pass `drop_extra_keys=True`. It drops unknown fields and returns a clean dictionary.

```python
from typing import TypedDict
from monk import validate_dict

class UserDict(TypedDict):
    name: str

payload = {"name": "John", "is_admin": True}

# ❌ Fails strict mode!
# validate_dict(payload, UserDict) 

# ✅ Returns sanitized dict: {"name": "John"}
safe_data = validate_dict(payload, UserDict, drop_extra_keys=True)
```

## Partial Validation (PATCH Requests)

Pass `partial=True` to ignore missing keys while still validating the keys that are present.

### Schema Composition

Use standard class inheritance to keep your rules DRY when building separate schemas for creation vs. partial updates.

```python
from typing import Annotated
from monk import validate_dict
from monk.constraints import Email, Interval, Len

class UserBase:
    age: Annotated[int, Interval(ge=18)]

# PATCH Schema (Inherits 'age', adds relaxed 'username', omits 'email')
class UserUpdate(UserBase):
    username: Annotated[str, Len(min_len=5)]

safe_patch = validate_dict({"username": "admin"}, UserUpdate, partial=True)
```

> ⚡ Explicit Nulls: `partial=True` only ignores completely omitted keys. If a client explicitly sends `{"username": None}`, it will still fail the `NotNull` check.

## Direct Execution (Standalone Variables)

Execute constraints directly on standalone variables.

> ⚡ Note: Direct execution raises standard ValueError or TypeError, not ValidationError.
> 
```python
from monk.constraints import Email, Interval

Email().validate("test@domain.com") # ✅ Success
Interval(ge=18).validate(12)        # ❌ ValueError
Email().validate(123)               # ❌ TypeError
```

## Validating Generators and Streams

Collection constraints (`Each`, `Contains`, `Unique`) reject exhaustible iterators to prevent silent data consumption.
To safely validate infinite streams or generators on the fly, use `validate_stream` (or `validate_async_stream`). Invalid items instantly raise a `ValidationError` before your application processes them.

```python
from typing import Iterator
from monk import validate_stream
from monk.constraints import Email

def process_data(stream: Iterator[str]):
    safe_stream = validate_stream(stream, Email)
    for item in safe_stream:
        print(item)

process_data((x for x in ["test@domain.com", "bad"]))
# Yields: test@domain.com
# ❌ Raises ValidationError on the second item!
```

## Deeply Nested Dictionaries

Use the `Nested` constraint to recursively validate complex JSON architectures without instantiating objects.

```python
from typing import TypedDict, Annotated
from monk import validate_dict
from monk.constraints import Email, Len, Each, Nested

class AddressDict(TypedDict):
    city: Annotated[str, Len(min_len=2)]

class UserDict(TypedDict):
    email: Annotated[str, Email]
    address: Annotated[AddressDict, Nested(AddressDict)]
    history: Annotated[list[AddressDict], Each(Nested(AddressDict))]
```

## Recursive Schemas

If you are building tree structures (like a file directory or a comment section), a schema might need to contain a `list` of itself. 

### With Raw Dictionaries (TypedDict)

Pass a lazy `lambda` to the `Nested` constraint to validate self-referencing schemas at runtime.

```python
from typing import TypedDict, Annotated
from monk import validate_dict
from monk.constraints import Len, Each, Nested

class Comment(TypedDict):
    text: Annotated[str, Len(min_len=1)]
    replies: Annotated[list["Comment"], Each(Nested(lambda: Comment))]
```

### With Dataclasses (@monk)

Recursive `@monk` dataclasses work out-of-the-box using standard string forward references. No `Nested` or `lambda` required.

```python
from typing import Annotated
from monk import monk, validate
from monk.constraints import Interval

@monk
class Node:
    id: Annotated[int, Interval(ge=1)]
    children: list["Node"]

validate(Node(id=1, children=[Node(id=2, children=[])])) 
```
