# Constraints

Every business rule in `iron-monk` is a **constraint**: a small class with a single `validate(value) -> None` method. Constraints are attached to type hints with `typing.Annotated`. They never coerce, never mutate, and never fail-fast — every error is collected.

This page is the catalog. For the design rationale, see **[Core Concepts](concepts.md)**.

---

## Anatomy of a Constraint

Every built-in constraint has a consistent shape:

```python
ConstraintName(
    # Constraint-specific arguments
    ...,
    # Optional kwargs available on every constraint
    message: str | None = None,
    code:    str | None = None,
)
```

- **`message`** — overrides the default error string. Supports `{value}` and `{field_name}` format placeholders for any constructor argument (e.g. `Interval(ge=18, message="Must be at least {ge}")`).
- **`code`** — overrides the machine-readable error code (defaults to the constraint class name). Useful for stable client-side error matching.

Most constraints also accept **`Ref(...)`** in place of literal values to reference sibling fields. See **[Cross-Field Validation](advanced/cross_field.md)**.

---

## Composition

`iron-monk` ships logical wrappers and per-element wrappers so any constraint can be lifted into a richer context.

### `AnyOf`

`AnyOf(*constraints, message=None, code=None)`

Passes if **at least one** wrapped constraint passes.

```python
from monk.constraints import AnyOf, Email, URL

contact: Annotated[str, AnyOf(Email, URL)]
```

### `AllOf`

`AllOf(*constraints, message=None, code=None)`

Passes only if **every** wrapped constraint passes. Equivalent to stacking them inside `Annotated`, but useful when you need to wrap a group as a single unit (e.g. inside `Not`, `AnyOf`, or `Each`).

```python
from monk.constraints import AllOf, LowerCase, Trimmed

name: Annotated[str, AllOf(LowerCase, Trimmed)]
```

### `Not`

`Not(constraint, *, message=None, code=None)`

Inverts a constraint. Fails when the wrapped constraint passes.

```python
from monk.constraints import Not, Email

not_an_email: Annotated[str, Not(Email)]
```

### `When`

`When(field, test, then, else_=None, *, message=None, code=None)`

Conditional validation. Resolves `field` (typically a `Ref` to a sibling field), runs `test` against it, and applies `then` to the **current** field's value when `test` passes. If `test` fails and `else_` is provided, `else_` is applied instead. See **[Cross-Field Validation](advanced/cross_field.md)** for end-to-end examples.

```python
from monk.constraints import When, Eq, Len, Ref

cc_number: Annotated[str, When(field=Ref("payment_method"), test=Eq("credit"), then=Len(min_len=16, max_len=16))]
```

### `Switch`

`Switch(field, cases, default=None, *, message=None, code=None)`

Multi-branch dispatch. Resolves `field` (typically a `Ref`) and applies the constraint mapped to that value in `cases`. Falls back to `default` when the discriminator is missing or unhashable; raises a `ValidationError` if neither matches. Sugar for chained `When` over a discriminated union.

```python
from monk.constraints import Switch, Email, Match, Len, Ref

target: Annotated[str, Switch(
    field=Ref("channel"),
    cases={"email": Email, "sms": Match(r"^\+\d+$")},
    default=Len(min_len=1),
)]
```

### Per-Element Validation

Annotate the element type directly. `iron-monk` synthesizes per-element rules at decoration time for `list`, `set`, `frozenset`, `tuple`, and `dict`:

```python
from typing import Annotated
from monk.constraints import Email, Interval, Len

emails: list[Annotated[str, Email]]
ages:   list[Annotated[int, Interval(ge=0)]]
mixed:  list[Annotated[int, Interval(gt=0)] | Annotated[str, Len(min_len=1)] | None]
pair:   tuple[Annotated[int, Interval(gt=0)], Annotated[str, Len(min_len=1)]]   # heterogeneous
links:  dict[Annotated[str, LowerCase], Annotated[str, URL]]
```

Use `T | None` inside the element annotation to allow `None` items.

### `Each`

`Each(*constraints)`

The explicit form. Reach for it when:

- The container is untyped (`list`, `dict`, plain `Annotated[list, ...]`).
- You want to layer **extra** rules on top of an inner-annotated container — supplying an outer `Each` short-circuits auto-synthesis to avoid double validation.
- You need the constraint as a value (e.g. inside `Not`, `AnyOf`, or as an argument to a custom helper).

Pass `Nullable` to allow `None` items, or `NotNull` to forbid them with a custom message.

```python
from monk.constraints import Each, Email, Nullable

emails: Annotated[list, Each(Email, Nullable)]   # untyped list
```

### `DictOf`

`DictOf(*, key=None, value=None, message=None, code=None)`

The explicit form for dictionaries. Use it for untyped `dict` fields, or to layer extra rules on top of an annotated `dict[K, V]`. Either side accepts a single constraint or an iterable.

```python
from monk.constraints import DictOf, LowerCase, URL

links: Annotated[dict, DictOf(key=LowerCase, value=URL)]
```

### `Predicate`

`Predicate(func, *, message=None, code=None)`

Wraps any boolean-returning callable as a constraint. The fastest path to one-off rules.

```python
from monk.constraints import Predicate

def is_even(n: int) -> bool:
    return n % 2 == 0

batch_size: Annotated[int, Predicate(is_even)]
```


---

## Nullability

Constraints are **required by default**. Two markers control optionality:

### `Nullable`

`Nullable()` — marker that allows `None`. Required inside `Each(...)` since `Each` evaluates its constraints functionally.

### `NotNull`

`NotNull(*, message=None, code=None)` — marker that forbids `None` and lets you customize the missing-value error message or code.

For top-level fields, prefer the standard `T | None` syntax — `iron-monk` natively intercepts `Union` and bypasses validation for missing data. Full discussion in **[Core Concepts → Nullability](concepts.md#nullability)**.

---

## Catalog

Constraints are grouped by data domain. Within each group, entries are alphabetized.

### Strings

#### `EndsWith`
`EndsWith(suffix, *, message=None, code=None)` — requires the value to end with `suffix`. Accepts `Ref`.

```python
avatar: Annotated[str, EndsWith(".png")]
```

#### `IsAlnum` · `IsAlpha` · `IsAscii` · `IsDigit` · `LowerCase` · `UpperCase`

Predicate-backed string property checks. No constructor — use the bare instance.

```python
from monk.constraints import LowerCase, IsDigit
slug: Annotated[str, LowerCase]
pin:  Annotated[str, IsDigit]
```

#### `Match`
`Match(pattern, *, message=None, code=None)` — requires the value to match a regex `pattern` (compiled once at construction).

```python
sku: Annotated[str, Match(r"^PROD-\d+$")]
```

#### `StartsWith`
`StartsWith(prefix, *, message=None, code=None)` — requires the value to start with `prefix`. Accepts `Ref`.

```python
category: Annotated[str, StartsWith("cat_")]
```

#### `Trimmed`
`Trimmed(*, message=None, code=None)` — rejects strings with leading or trailing whitespace.

```python
name: Annotated[str, Trimmed]
```

---

### Format & Identity

Format-style string validators that check structural correctness only. They never coerce.

#### `Base64`
`Base64(*, message=None, code=None)` — structurally validates a Base64 string.

#### `Email`
`Email(*, message=None, code=None)` — RFC-style structural email check.

```python
email: Annotated[str, Email]
```

#### `HexColor`
`HexColor(*, message=None, code=None)` — `#RGB`, `#RGBA`, `#RRGGBB`, or `#RRGGBBAA`.

#### `IPAddress`
`IPAddress(*, message=None, code=None)` — IPv4 or IPv6.

#### `IsISO8601`
`IsISO8601(*, message=None, code=None)` — ISO 8601 date or datetime string. **Does not coerce** to a `datetime`.

#### `JSON`
`JSON(*, message=None, code=None)` — accepts only strings that successfully parse as JSON. Does not return the parsed value.

#### `JWT`
`JWT(*, message=None, code=None)` — JSON Web Token shape (`header.payload.signature`). Structural only — no signature verification.

#### `MacAddress`
`MacAddress(*, message=None, code=None)` — `00:1A:2B:3C:4D:5E` or `-` separator.

#### `SemVer`
`SemVer(*, message=None, code=None)` — Semantic Versioning string.

#### `Slug`
`Slug(*, message=None, code=None)` — URL-safe slug (lowercase alphanumerics and hyphens).

#### `URL`
`URL(*, message=None, code=None)` — scheme + netloc check.

#### `UUID`
`UUID(*, message=None, code=None)` — UUID string or native `uuid.UUID`.

```python
import uuid
node_id: Annotated[str | uuid.UUID, UUID]
```

---

### Numeric

#### `Interval`
`Interval(*, gt=None, ge=None, lt=None, le=None, message=None, code=None)` — comparable bounds. Any combination of bounds is valid. All bounds accept `Ref`.

```python
quantity: Annotated[int, Interval(gt=0, le=100)]
```

#### `IsFinite` · `IsInfinite` · `IsNan`

Predicate-backed math checks for floats. Use bare instances.

```python
ratio: Annotated[float, IsFinite]
```

#### `MultipleOf`
`MultipleOf(multiple_of, *, message=None, code=None)` — value must be exactly divisible. Accepts `Ref`.

```python
pack_size: Annotated[int, MultipleOf(5)]
```

#### `NonNegative`

Pre-instantiated alias for `Interval(ge=0)`. Use bare.

```python
score: Annotated[int, NonNegative]
```

#### `Port`
`Port(*, message=None, code=None)` — integer in `[1, 65535]`.

```python
db_port: Annotated[int, Port]
```

---

### Equality & Choice

#### `Eq`
`Eq(value, *, message=None, code=None)` — strict equality (`==`). Accepts `Ref`.

```python
status: Annotated[str, Eq("active")]
```

#### `OneOf`
`OneOf(choices, *, message=None, code=None)` — value must be a member of `choices`. Accepts `Ref`.

```python
role: Annotated[str, OneOf(["admin", "editor", "viewer"])]
```

---

### Collections

#### `Contains`
`Contains(item, *, message=None, code=None)` — collection or string must contain `item` / substring. Accepts `Ref`.

```python
categories: Annotated[list[str], Contains("default")]
```

#### `ContainsKeys`
`ContainsKeys(keys, *, message=None, code=None)` — dict must include all `keys`. Accepts `Ref`.

```python
payload: Annotated[dict, ContainsKeys(["id", "type"])]
```

#### `CSV`
`CSV(*constraints, separator=",", unique=False, message=None, code=None)` — splits a delimited string in place and applies `constraints` to each element. Composes recursively (`CSV(CSV(...), ...)`).

```python
tags: Annotated[str, CSV(LowerCase, Len(min_len=2), separator=",")]
matrix: Annotated[str, CSV(CSV(LowerCase, separator="|"), separator=",")]
```

#### `ExactLen`
`ExactLen(length, *, message=None, code=None)` — exact length. Accepts `Ref`.

```python
pin: Annotated[str, ExactLen(4)]
```

#### `Len`
`Len(min_len=0, max_len=None, *, message=None, code=None)` — bounded length. Both bounds accept `Ref`.

```python
tags: Annotated[list[str], Len(min_len=1, max_len=10)]
```

#### `Nested`
`Nested(schema, partial=False, *, message=None, code=None)` — validates a raw dict against another `TypedDict` / `@monk` class. Use `partial=True` for PATCH-style payloads.

```python
class AddressDict(TypedDict):
    city: str

address: Annotated[AddressDict, Nested(AddressDict)]
```

#### `Subset`
`Subset(choices, *, message=None, code=None)` — every element must lie within `choices`. Accepts `Ref`. Backed by a `frozenset` for O(n) checks.

```python
permissions: Annotated[list[str], Subset(["read", "write", "execute"])]
```

#### `Unique`
`Unique(*, message=None, code=None)` — all elements distinct. Falls back gracefully for unhashable items.

```python
matrix: Annotated[list[list[int]], Unique]
```

---

### Datetime

#### `Future`
`Future(*, message=None, code=None)` — `datetime` / `date` strictly in the future.

#### `IsUTC`

Predicate-backed marker. Requires a tz-aware `datetime` whose offset is exactly UTC.

```python
created_at: Annotated[datetime.datetime, IsUTC]
```

#### `Past`
`Past(*, message=None, code=None)` — `datetime` / `date` strictly in the past.

```python
dob: Annotated[datetime.date, Past]
```

---

### Schedule

#### `Cron`
`Cron(*, allow_aws=False, message=None, code=None)` — structurally validates a cron expression. Set `allow_aws=True` to accept the AWS EventBridge 6-field format.

```python
standard:  Annotated[str, Cron()]
eventbridge: Annotated[str, Cron(allow_aws=True)]
```

---

### Filesystem

#### `IsDir`
`IsDir(*, message=None, code=None)` — `str` or `pathlib.Path` pointing to an existing directory.

#### `IsFile`
`IsFile(*, message=None, code=None)` — `str` or `pathlib.Path` pointing to an existing file.

```python
config: Annotated[pathlib.Path, IsFile]
```

---

### Geospatial

#### `LatLong`
`LatLong(*, message=None, code=None)` — sequence of exactly two floats: `(lat, long)`, with `lat ∈ [-90, 90]` and `long ∈ [-180, 180]`.

```python
coords: Annotated[tuple[float, float], LatLong]
```

---

## Custom Messages and Codes

Every constraint accepts `message=` and `code=`. Messages support format placeholders for any constructor argument plus `{value}`:

```python
age: Annotated[int, Interval(ge=18, message="Must be at least {ge}, got {value}")]
```

The placeholder set is built from the constraint instance's fields, so `{ge}`, `{lt}`, `{multiple_of}`, `{prefix}`, etc. all resolve.

---

## Custom Constraints

The `MonkConstraint` protocol is one method. Use `@constraint` to define your own:

```python
from monk import constraint

@constraint
class Even:
    message: str | None = None

    def validate(self, value: int) -> None:
        if value % 2 != 0:
            raise ValueError("Must be even.")
```

Full guide: **[Customization](advanced/customization.md)**.

---

## Next Steps

- **[Cross-Field Validation](advanced/cross_field.md)** — `Ref` and the `__monk_validate__` hook.
- **[Customization](advanced/customization.md)** — building reusable constraints in 3 lines.
- **[Settings & Type Metadata](advanced/settings.md)** — wrappers, sentinels, env vars for framework integration.
