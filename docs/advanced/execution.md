# Execution Models

`iron-monk` exposes three validation entry points. The basics are covered in **[Core Concepts → Validation](../concepts.md#3-validation)**; this page documents the flags, edge cases, and recursion patterns power users hit in production.

---

## `validate_dict` — Strict Mode and Sanitization

By default, `validate_dict` is **strict**: any key in the payload that is not in the schema raises a `ValidationError`. Pass `drop_extra_keys=True` to silently strip them and return a sanitized dict.

```python
from typing import TypedDict
from monk import validate_dict

class UserDict(TypedDict):
    name: str

payload = {"name": "John", "is_admin": True}

# validate_dict(payload, UserDict)            # raises — "is_admin" rejected
clean = validate_dict(payload, UserDict, drop_extra_keys=True)
# {"name": "John"}
```

Use `drop_extra_keys=True` at the trust boundary (HTTP handlers, queue consumers) to defang attacker-controlled payloads before they reach your domain layer.

---

## `validate_dict` — Partial Validation (PATCH)

For PATCH-style endpoints where the client sends only the fields they want to change, pass `partial=True`. Missing keys are skipped; present keys are validated as usual.

```python
from typing import Annotated
from monk import validate_dict
from monk.constraints import Email, Interval, Len

class UserBase:
    age: Annotated[int, Interval(ge=18)]

class UserUpdate(UserBase):
    username: Annotated[str, Len(min_len=5)]

validate_dict({"username": "admin"}, UserUpdate, partial=True)
```

**Partial does not relax NotNull.** `partial=True` only ignores *omitted* keys. A client that explicitly sends `{"username": None}` still fails the `NotNull` check — explicit nulls remain semantically distinct from missing fields.

Use ordinary class inheritance (`UserUpdate(UserBase)`) to keep PATCH schemas DRY against creation schemas.

---

## `validate_stream` — Lazy Iteration

Collection constraints (`Each`, `Contains`, `Unique`) refuse to consume exhaustible iterators — they would silently destroy the data they were validating. To validate a stream lazily, use `validate_stream` (or `validate_async_stream`):

```python
from collections.abc import Iterator
from monk import validate_stream
from monk.constraints import Email

def process(stream: Iterator[str]) -> None:
    for email in validate_stream(stream, Email):
        send(email)

process(x for x in ["test@domain.com", "bad"])
# yields "test@domain.com", then raises ValidationError on "bad"
```

The async sibling has the same shape:

```python
from monk import validate_async_stream

async def process(stream):
    async for email in validate_async_stream(stream, Email):
        await send(email)
```

Each item is validated as it is pulled — no buffering, no peeking ahead. Failures interrupt iteration immediately.

---

## Standalone Execution

Every constraint exposes `.validate(value)`. Calling it directly is the fastest path for one-off checks at function boundaries or in tests:

```python
from monk.constraints import Email, Interval

Email().validate("test@domain.com")          # passes silently
Interval(ge=18).validate(12)                 # raises ValueError
Email().validate(123)                        # raises TypeError
```

Standalone calls raise native `ValueError` / `TypeError` rather than `ValidationError` — there is no field context to aggregate over. If you need aggregation in tests, build a `@monk` class and call `validate()`.

---

## Nested Schemas

Use `Nested(schema)` to validate raw nested dicts against another `TypedDict` or `@monk` class without instantiating them.

```python
from typing import TypedDict, Annotated
from monk import validate_dict
from monk.constraints import Email, Len, Nested

class AddressDict(TypedDict):
    city: Annotated[str, Len(min_len=2)]

class UserDict(TypedDict):
    email: Annotated[str, Email]
    address: Annotated[AddressDict, Nested(AddressDict)]
    history: list[Annotated[AddressDict, Nested(AddressDict)]]   # auto-synth handles per-element
```

`Nested` accepts `partial=True` to propagate PATCH semantics into nested dicts.

---

## Recursive Schemas

### TypedDict (lazy reference)

`TypedDict` cannot reference itself directly. Pass a lambda to `Nested` so resolution happens at validation time:

```python
from typing import TypedDict, Annotated
from monk.constraints import Len, Each, Nested

class Comment(TypedDict):
    text: Annotated[str, Len(min_len=1)]
    replies: Annotated[list["Comment"], Each(Nested(lambda: Comment))]
```

### `@monk` Dataclass (string forward reference)

`@monk` dataclasses handle recursion natively via standard string forward references. No `Nested`, no lambda:

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

The recursion is bounded by your data, not your annotation — there is no cycle detection. Trust the data shape, or add a depth check in `__monk_validate__`.
