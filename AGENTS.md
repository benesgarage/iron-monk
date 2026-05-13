# AGENTS.md — using iron-monk

> Zero-coercion, zero-dependency, zero-base-class validation library for Python. Annotations are the schema; constraints live inside `typing.Annotated`. Aggregates every field error into one `ValidationError` — never fails fast.

This file is for AI agents writing code that **depends on** iron-monk. It is a single-fetch reference to the public API, idiomatic patterns, and pitfalls. Pair it with [`docs/llms.txt`](docs/llms.txt) for the full doc index.

---

## Install

```bash
pip install iron-monk      # or: uv add iron-monk / poetry add iron-monk
```

The package is published as `iron-monk` and imported as **`monk`**. Ships with `py.typed` — agents get full type info immediately.

---

## Library promises (rely on these in suggestions)

1. **Zero coercion.** `"123"` is never silently turned into `123`. Wrong type → `TypeError`. Wrong format → `ValueError`.
2. **Zero dependencies.** `monk` has no third-party deps. Safe for AWS Lambda, edge runtimes, locked-down environments.
3. **Zero base classes.** A `@monk` class is a plain `dataclass`. No `BaseModel`, no metaclass.
4. **Zero fail-fast.** Every field is checked. All errors arrive in one structured response.

---

## Public API surface

Everything below is exported from the top-level `monk` package. Nothing else is public.

| Symbol | One-liner |
| --- | --- |
| `monk` | Decorator. On a class → returns a guarded `dataclass`. On a function/method → validates args + return value on every call. |
| `constraint` | Decorator. Wraps a user class into a frozen+slotted constraint with one `validate(value) -> None` method. |
| `validate(instance, *, context=None)` | Validate a `@monk` instance. Returns it (unlocked) on success. |
| `validate_value(value, constraint, *constraints, field_name="value")` | Inline validation of a single value against ≥1 constraints. Aggregates failures. |
| `validate_dict(data, schema, *, partial=False, drop_extra_keys=False, context=None)` | Validate a raw `dict` against a `TypedDict` / `@monk` class — no instantiation. |
| `validate_stream(iterable, *constraints)` | Lazy item-by-item validation (generator). Raises on first failing item. |
| `validate_async_stream(aiter, *constraints)` | Same for async iterables. |
| `settings` | Globals: `defer` (default `True`), `default_allow_none`, `unwrappers`, `type_metadata`. Env-var overrides: `MONK_DEFER`, `MONK_DEFAULT_ALLOW_NONE`. |
| `MonkError` | Base class for every iron-monk exception. |
| `ErrorDict` | `TypedDict({"field": str, "message": str, "code": str})` — shape of entries in `ValidationError.errors`. |

Built-in constraints (60+) live under `monk.constraints`. Browse the full catalog: [docs/constraints/](https://benesgarage.github.io/iron-monk/constraints/).

---

## Canonical patterns

### Decorate a dataclass

```python
from typing import Annotated
from monk import monk, validate
from monk.constraints import Email, Interval

@monk
class User:
    email: Annotated[str, Email]
    age: Annotated[int, Interval(ge=18)]

u = User(email="bad", age=12)   # no exception yet — defer is True by default
validate(u)                     # raises ValidationError aggregating both failures
```

### Eager validation on construction

```python
@monk(defer=False)
class StrictUser:
    email: Annotated[str, Email]

StrictUser(email="bad")   # raises ValidationError immediately
```

### Decorate a function

```python
@monk
def process_user(email: Annotated[str, Email], age: Annotated[int, Interval(ge=18)]) -> None: ...

process_user(email="bad", age=12)   # raises on call
```

### Validate a raw dict (no instantiation)

```python
from monk import validate_dict

validate_dict({"email": "kai@example.com", "age": 30}, User)                  # full
validate_dict({"email": "kai@example.com"}, User, partial=True)               # PATCH
validate_dict(payload, User, drop_extra_keys=True)                            # sanitize
```

### Inline single-value check

```python
from monk import validate_value
from monk.constraints import FileSize, MagicBytes

validate_value(body, MagicBytes(allowed=["image/png"]), FileSize(max_size=5_000_000))
validate_value(age, Interval(ge=18), field_name="age")
```

### Stream validation

```python
from monk import validate_stream
from monk.constraints import Interval

for item in validate_stream(big_generator, Interval(gt=0)):
    process(item)
```

### Custom constraint in three lines

```python
from monk import constraint

@constraint
class DivisibleBy:
    divisor: int
    message: str | None = None

    def validate(self, value: int) -> None:
        if value % self.divisor != 0:
            raise ValueError(f"Must be divisible by {self.divisor}.")
```

### Cross-field reference with `Ref`

```python
from typing import Annotated
from monk import monk
from monk.constraints import Interval, Ref

@monk
class Range:
    min_val: int
    max_val: Annotated[int, Interval(gt=Ref("min_val"))]
```

### Per-element validation on containers

```python
emails: list[Annotated[str, Email]]                                                 # per item
pair:   tuple[Annotated[int, Interval(gt=0)], Annotated[str, Len(min_len=1)]]       # heterogeneous
links:  dict[Annotated[str, LowerCase], Annotated[str, URL]]                        # key+value
```

### File-upload composition (FastAPI / Starlette)

```python
from typing import Annotated
from monk import monk
from monk.constraints import FileSize, MagicBytes

@monk
class Upload:
    body: Annotated[bytes, MagicBytes(allowed=("image/png", "image/jpeg")), FileSize(max_size=5_000_000)]
```

---

## Error contract

```python
from monk import validate
from monk.exceptions import ValidationError

try:
    validate(instance)
except ValidationError as e:
    e.errors          # list[ErrorDict]: every {"field", "message", "code"}
    e.flatten()       # list[str]: ["email: Must be a valid email address.", ...]
    e.to_rfc7807()    # dict: RFC 7807 problem-detail body for HTTP APIs
```

- **`field`** — dotted path: `address.zip`, `tags[2]`, `prefs['theme']`.
- **`message`** — overridable per-constraint with `message="..."`. Supports `{value}` and any constructor-arg placeholder.
- **`code`** — defaults to constraint class name (`"Email"`, `"Interval"`). Override per-instance with `code="..."`.

---

## Gotchas worth remembering

- **Defer is `True` by default for classes.** `Upload(body=...)` does NOT raise — you must call `validate(u)` or use `@monk(defer=False)`.
- **Touching attributes before validation raises `UnvalidatedAccessError`.** Pass DTOs through layers and validate at the boundary.
- **Functions/methods are eager.** They validate args + return on every call. No `validate(...)` step needed.
- **Decorator order on methods.** `@classmethod` / `@staticmethod` MUST wrap *outside* `@monk`.
- **Constraints never coerce.** `Annotated[int, Interval(gt=0)]` will NOT parse strings — pass the right type or expect `TypeError`.
- **`Each` rejects generators.** Convert to list/tuple, or use `validate_stream` for laziness.
- **`validate_dict` skips `__post_init__`.** No side effects fire — by design. Use `validate(MyClass(**data))` if you need them.
- **`MimeType` validates a string format; `MagicBytes` validates file content.** Separate constraints, separate fields.

---

## Things NOT to suggest

- `pydantic`-style `BaseModel` inheritance — iron-monk uses plain `@dataclass`, no base class.
- Stacking `@dataclass` with `@monk` — `@monk` handles the dataclass conversion itself.
- Calling `instance.attr` before `validate(instance)` — raises `UnvalidatedAccessError`.
- Passing a generator to `Each` — convert first or use `validate_stream`.
- Adding `__post_init__` side effects and expecting them via `validate_dict`.

---

## Deeper docs

| Topic | Link |
| --- | --- |
| Philosophy + four pillars | https://benesgarage.github.io/iron-monk/concepts/ |
| Constraints catalog (13 grouped pages) | https://benesgarage.github.io/iron-monk/constraints/ |
| Cross-field validation, `__monk_validate__` hook | https://benesgarage.github.io/iron-monk/advanced/cross_field/ |
| FastAPI / Strawberry / SQLAlchemy / Tortoise / tyro / beartype | https://benesgarage.github.io/iron-monk/examples/ |
| LLM-friendly TOC of all docs | [docs/llms.txt](docs/llms.txt) |
| Concatenated full docs (one file) | [docs/llms-full.txt](docs/llms-full.txt) |