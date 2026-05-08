# Core Concepts

`iron-monk` is built on four pillars: **the decorator**, **constraints**, **validation**, and **errors**. Before the deep-dive, a short note on the philosophy that ties them together — the *why* behind the design.

## Philosophy

Most validation libraries do too much. They coerce `"123"` into `123`, force you to inherit from a base class, and crash on the first error so you debug your payload one field at a time.

`iron-monk` flips all three:

- **Zero coercion.** If a string is not the right format, that is an error. Your data is never silently rewritten.
- **Zero base classes.** A `@monk` class is still a plain Python `dataclass`. No `BaseModel`, no metaclass tricks, no IDE slowdown.
- **Zero fail-fast.** Every field is checked. You get *every* error in one shot — no playing whack-a-mole.
- **Annotation is the schema.** Constraints live inside `typing.Annotated`. There is no separate model layer to keep in sync with your types.

Each pillar below reflects one of these choices.

---

## 1. The `@monk` Decorator

The single entry point for binding constraints to your code. It adapts to what it wraps.

### Why

Most validators force you to choose an architecture: a `BaseModel` for objects, a `Schema` class for dicts, a `validator()` decorator for functions. `@monk` is one decorator that covers all three surfaces — and on classes, it returns a regular `dataclass`, so the rest of your code does not need to know `monk` exists.

### How

| Wraps | Effect |
| --- | --- |
| `class` | Becomes a `@dataclass`. Validation is **deferred** by default — you call `validate(instance)` explicitly. Attribute access is locked until then. |
| `def` / `async def` | Wraps the call. Arguments and return value are validated **eagerly** on every invocation. |
| Method | Same as a function. Always place `@monk` *below* `@classmethod` / `@staticmethod`. |

```python
from monk import monk

@monk                          # deferred — call validate(user) yourself
class User: ...

@monk(defer=False)             # eager — fails inside __post_init__
class StrictUser: ...

@monk
def process_user(...): ...     # eager — fails on every call
```

### Gotchas

- **Deferred is the default for classes.** Touching `user.email` before `validate(user)` raises `UnvalidatedAccessError`. This is intentional: it lets you pass DTOs through layers and validate at the boundary (e.g. just before a DB write).
- **Globals.** `MONK_DEFER=false` (env var) or `settings.defer = False` (code) flip the default for the whole process.
- **Decorator order matters on methods.** `@classmethod` / `@staticmethod` must wrap *outside* `@monk`, otherwise binding breaks.

---

## 2. Constraints

The business rules themselves — `Email`, `Interval`, `Len`, etc.

### Why

A constraint is just a class with one method: `validate(value) -> None`. That is the entire protocol. Anything that satisfies it can be used as a constraint — no registry, no metaclass, no plugin system. The toolkit stays small and trivially extensible.

### How

Stack constraints inside `typing.Annotated`. They run independently, in order, against the same value.

=== "Strings"
    ```python
    from typing import Annotated
    from monk.constraints import Len, LowerCase, Regex

    Username = Annotated[str, Len(min_len=5, max_len=20), LowerCase, Regex(r"^\S+$")]
    ```

=== "Numbers"
    ```python
    from typing import Annotated
    from monk.constraints import Interval, MultipleOf

    Score = Annotated[int, Interval(gt=0, le=100), MultipleOf(2)]
    ```

=== "Collections"
    ```python
    from typing import Annotated
    from monk.constraints import Email, Len

    ContactList = Annotated[list[Annotated[str, Email]], Len(min_len=1, max_len=5)]
    ```

Constraints also compose with logical wrappers (`AnyOf`, `AllOf`, `Not`) and per-element wrappers (`Each`, `DictOf`). See **[Constraints → Composition](constraints.md#composition)**.

**Per-element rules go inside the element type.** `iron-monk` recognizes annotated element types inside `list`, `set`, `tuple`, and `dict` and validates each item automatically:

```python
items: list[Annotated[int, Interval(gt=0)]]
mixed: list[Annotated[int, Interval(gt=0)] | Annotated[str, Len(min_len=1)] | None]
pair:  tuple[Annotated[int, Interval(gt=0)], Annotated[str, Len(min_len=1)]]
links: dict[Annotated[str, LowerCase], Annotated[str, URL]]
```

Reach for the explicit `Each(...)` / `DictOf(...)` wrappers only when the container is untyped or you need to layer extra rules. See **[Constraints → Composition](constraints.md#composition)**.

### Nullability

Constraints are **required by default**. Passing `None` to a constrained field raises a `NotNull` error.

```python
from typing import Annotated
from monk import monk
from monk.constraints import Email, Each, Len, Nullable, NotNull

@monk
class Profile:
    email: Annotated[str, Email]                                              # (1)!
    nickname: Annotated[str, Len(max_len=10)] | None = None                   # (2)!
    phone: Annotated[str, NotNull(message="Phone is required!"), Len(10)]     # (3)!
    tags: Annotated[list[str | None], Each(Nullable, Len(max_len=5))]         # (4)!
```

1. Required. `None` raises `NotNull`.
2. Optional. `iron-monk` natively intercepts `| None` — no `Nullable` constraint needed at the field level.
3. Custom error message / code for missing data.
4. Inside `Each(...)` you must opt in with `Nullable` because `Each` runs constraints functionally over items.

??? info "Global Nullability (type-checker integration)"
    To let a runtime type checker (e.g. `beartype`) own required-field enforcement, flip the default:

    ```bash
    export MONK_DEFAULT_ALLOW_NONE=true
    ```

    ```python
    from monk import settings
    settings.default_allow_none = True
    ```

### Cross-field rules

Constraints can reference *sibling* fields with `Ref(...)`:

```python
from typing import Annotated
from monk import monk
from monk.constraints import Interval, Ref

@monk
class Range:
    min_val: int
    max_val: Annotated[int, Interval(gt=Ref("min_val"))]
```

`Ref` is resolved at validation time. See **[Cross-Field Validation](advanced/cross_field.md)** for the full mechanic and the `__monk_validate__` hook.

### Custom constraints

The protocol is one method. To define your own, use the `@constraint` decorator:

```python
from monk import constraint

@constraint
class Even:
    message: str | None = None

    def validate(self, value):
        if value % 2 != 0:
            raise ValueError("Must be even.")
```

See **[Customization](advanced/customization.md)** for message templating, code overrides, and refs in custom constraints.

### Gotchas

- **Constraints never coerce.** `Annotated[int, Interval(gt=0)]` does *not* parse strings. Pass the right type or expect a `TypeError`.
- **Order matters when constraints share a domain.** `Len(min_len=3)` before `LowerCase` will fail length first, lower-case second. Stable, but worth knowing.
- **`Each` does not consume iterators.** Passing a generator raises — convert to a list/tuple first, or use `validate_stream` (see Pillar 3).

---

## 3. Validation

Three entry points. Pick the one matching the data shape, not the framework.

### Why

Different stages of an application care about different shapes. Inside a service, you have objects. At an HTTP boundary, you have raw dicts. In a data pipeline, you have streams. Forcing all three to go through one entry point would mean instantiating objects you do not need or losing laziness.

### How

| Function | Input | When to use |
| --- | --- | --- |
| `validate(instance)` | A `@monk` class instance | Validate DTOs you have already built. Returns the (now-unlocked) instance for inline use. |
| `validate_dict(data, schema)` | A raw `dict` + `TypedDict` / `@monk` class | High-throughput APIs that never instantiate objects. Supports `partial=True` (PATCH) and `drop_extra_keys=True` (sanitization). |
| `validate_stream(iterable, constraints)` | A generator / iterator | Lazy validation of large streams. The async sibling is `validate_async_stream`. |

```python
from monk import validate, validate_dict, validate_stream

# Object: deferred until called explicitly
user = User(email="kai@example.com", age=30)
validate(user)

# Dict: skip instantiation entirely
validate_dict({"email": "kai@example.com", "age": 30}, User)

# Stream: validate items as they are pulled
for item in validate_stream(big_generator, [Interval(gt=0)]):
    process(item)
```

### Gotchas

- **`validate(instance)` is a no-op for non-monk classes.** It raises `TypeError` to surface accidental misuse rather than silently passing.
- **`validate_dict` does not allocate the object.** Side effects in `__post_init__` will *not* fire — that is by design. Use `validate(MyClass(**data))` if you need them.
- **Streams are exhausted.** `validate_stream` yields each validated item; consume the generator.

---

## 4. Errors

The unique selling point. Every other library on the JVM/Rust/Python market fails fast. `iron-monk` does not.

### Why

When a payload has three bad fields, your user wants to know all three at once, not one at a time as they fix each. Aggregation is the difference between a usable API and a frustrating one.

### How

A failed validation raises a single `ValidationError` carrying a list of `ErrorDict`:

```python
from monk import validate
from monk.exceptions import ValidationError

try:
    validate(User(email="bad-email", age=12))
except ValidationError as e:
    print(len(e.errors))       # 2 — both email and age are reported
    print(e.errors[0])         # {"field": "email", "message": "...", "code": "Email"}
    print(e.flatten())         # ["email: Must be a valid email address.", "age: ..."]
    print(e.to_rfc7807())      # RFC 7807 problem-detail dict for HTTP APIs
```

Each `ErrorDict` carries:

- **`field`** — dotted path to the offending field. Nested fields look like `address.zip`; list items like `tags[2]`; dict values like `prefs['theme']`.
- **`message`** — human-readable, overridable per-constraint with `message=...`.
- **`code`** — stable machine-readable identifier (the constraint class name by default, or a custom `code=...`).

### Gotchas

- **Standalone `Constraint.validate()` is *not* aggregated.** It raises native `ValueError` / `TypeError` because there is no field context to aggregate over. Aggregation is a property of `validate` / `validate_dict` / function-mode `@monk`.
- **`to_rfc7807()` defaults to HTTP 400.** Pass `status=`, `title=`, `type_uri=`, `instance=` to customize per route.
- **Error codes are class names by default.** If you alias a constraint (`MyEmail = Email`), the code stays `"Email"`. To override, set `code="..."` on the constraint instance.

---

## Next Steps

- **[Constraints Toolkit](constraints.md)** — every built-in constraint with examples.
- **[Cross-Field Validation](advanced/cross_field.md)** — `Ref` and the `__monk_validate__` hook.
- **[Customization](advanced/customization.md)** — defining your own constraints in three lines.
- **[Settings & Type Metadata](advanced/settings.md)** — unwrappers, type-keyed metadata, env vars for framework integration.
