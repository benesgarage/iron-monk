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

!!! tip "Bytes are accepted too"
    Every string-typed constraint in this section (and Format & Identity below) accepts `bytes` and `bytearray` in addition to `str`. Inputs are decoded as UTF-8 before validation; invalid UTF-8 raises a `ValueError`. This lets you validate raw network/protobuf payloads without manually decoding first.



#### `EndsWith`
`EndsWith(suffix, *, message=None, code=None)` — requires the value to end with `suffix`. Accepts `Ref`.

```python
avatar: Annotated[str, EndsWith(".png")]
```

#### `HexString`
`HexString(length=None, *, message=None, code=None)` — value contains only hexadecimal characters. If `length` is set, the string must match it exactly.

```python
session_token: Annotated[str, HexString(length=64)]
```

#### `IsAlnum` · `IsAlpha` · `IsAscii` · `IsDigit` · `LowerCase` · `Printable` · `UpperCase`

Predicate-backed string property checks. No constructor — use the bare instance. `Printable` rejects control characters (`\x00-\x1f`, `\x7f`); empty strings pass.

```python
from monk.constraints import LowerCase, IsDigit, Printable
slug:        Annotated[str, LowerCase]
pin:         Annotated[str, IsDigit]
display:     Annotated[str, Printable]
```

#### `Match`
`Match(pattern, *, message=None, code=None)` — requires the value to match a regex `pattern` (compiled once at construction).

```python
sku: Annotated[str, Match(r"^PROD-\d+$")]
```

#### `MaxBytes`
`MaxBytes(max_bytes, *, message=None, code=None)` — UTF-8 encoded length must not exceed `max_bytes`. Accepts `str` (encoded to count) or raw `bytes` / `bytearray` (counted directly). Use for database column limits and API payload guards where character count diverges from byte count (CJK, emoji, accented Latin).

```python
bio: Annotated[str, MaxBytes(280)]
```

#### `NoWhitespace`
`NoWhitespace(*, message=None, code=None)` — rejects strings containing any whitespace character (space, tab, newline, etc.).

```python
username: Annotated[str, NoWhitespace]
```

#### `PathSafe`
`PathSafe(*, message=None, code=None)` — filename hardening: rejects path separators (`/`, `\`), null bytes, parent refs (`..`), the literal `.`/`..` filenames, and empty strings. Use for user-uploaded filenames, S3 key segments, traversal prevention.

```python
upload_name: Annotated[str, PathSafe]
```

#### `SingleLine`
`SingleLine(*, message=None, code=None)` — rejects strings containing `\n` or `\r`. Tabs and other whitespace are allowed.

```python
log_message: Annotated[str, SingleLine]
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

#### `DataURI`
`DataURI(*, message=None, code=None)` — RFC 2397 data URI (e.g., `data:image/png;base64,iVBOR...`). Structural only; does not decode the payload.

```python
embedded_image: Annotated[str, DataURI]
```

#### `CreditCard`
`CreditCard(*, message=None, code=None)` — 13-19 digit string passing the Luhn checksum. Spaces and dashes are tolerated. Structural only — no issuer/network check.

```python
card_number: Annotated[str, CreditCard]
```

#### `Email`
`Email(*, message=None, code=None)` — RFC-style structural email check.

```python
email: Annotated[str, Email]
```

#### `Hash`
`Hash(algorithm, *, message=None, code=None)` — hex digest of fixed length per algorithm. Supported: `md5`, `sha1`, `sha224`, `sha256`, `sha384`, `sha512`, `blake2s`, `blake2b`. Algorithm name is case-insensitive.

```python
content_sha256: Annotated[str, Hash("sha256")]
```

#### `HexColor`
`HexColor(*, message=None, code=None)` — `#RGB`, `#RGBA`, `#RRGGBB`, or `#RRGGBBAA`.

#### `Hostname`
`Hostname(*, message=None, code=None)` — RFC 1123 hostname: each label 1-63 chars (alphanum + hyphen, no leading/trailing hyphen), total ≤253 chars. Single-label hostnames like `localhost` pass.

```python
host: Annotated[str, Hostname]
```

#### `HttpURL`
`HttpURL(*, message=None, code=None)` — URL restricted to the `http` or `https` scheme. Use this when you specifically want to reject `ftp://`, `file://`, `javascript:`, etc.

```python
webhook_url: Annotated[str, HttpURL]
```

#### `IPAddress`
`IPAddress(*, message=None, code=None)` — IPv4 or IPv6.

#### `ISBN`
`ISBN(*, message=None, code=None)` — ISBN-10 or ISBN-13 with checksum verification. Spaces and dashes are tolerated; the trailing `X` check character is accepted for ISBN-10.

```python
book_isbn: Annotated[str, ISBN]
```

#### `IsISO8601`
`IsISO8601(*, message=None, code=None)` — ISO 8601 date or datetime string. **Does not coerce** to a `datetime`.

#### `JSON`
`JSON(*, message=None, code=None)` — accepts only strings that successfully parse as JSON. Does not return the parsed value.

#### `JWT`
`JWT(*, message=None, code=None)` — JSON Web Token shape (`header.payload.signature`). Structural only — no signature verification.

#### `MacAddress`
`MacAddress(*, message=None, code=None)` — `00:1A:2B:3C:4D:5E` or `-` separator.

#### `MimeType`
`MimeType(*, message=None, code=None)` — RFC 6838 `type/subtype` with optional `; param=value` parameters.

```python
content_type: Annotated[str, MimeType]
```

#### `PEMBlock`
`PEMBlock(*, message=None, code=None)` — structurally validates a PEM-encoded block (X.509 cert, RSA/SSH key, etc.). Verifies the `-----BEGIN <LABEL>-----` / `-----END <LABEL>-----` envelope matches and the body contains Base64 content. **Performs no cryptographic verification** — use a crypto library for that.

```python
cert: Annotated[str, PEMBlock]
```

#### `PhoneE164`
`PhoneE164(*, message=None, code=None)` — structural [E.164](https://en.wikipedia.org/wiki/E.164) phone number: leading `+`, 1-15 digits, no separators. Structural only — no carrier/region lookup.

```python
phone: Annotated[str, PhoneE164]
```

#### `SemVer`
`SemVer(*, message=None, code=None)` — Semantic Versioning string.

#### `Slug`
`Slug(*, message=None, code=None)` — URL-safe slug (lowercase alphanumerics and hyphens).

#### `TimeOfDay`
`TimeOfDay(*, message=None, code=None)` — 24-hour `HH:MM` or `HH:MM:SS` time string. Does not validate full datetimes — see `IsISO8601` for that.

```python
opening_hour: Annotated[str, TimeOfDay]
```

#### `TimezoneName`
`TimezoneName(*, message=None, code=None)` — IANA timezone name (e.g., `America/New_York`, `Europe/Berlin`, `UTC`). Resolved via `zoneinfo.ZoneInfo`; `zoneinfo` is imported lazily.

```python
display_tz: Annotated[str, TimezoneName]
```

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

#### `DecimalPlaces`
`DecimalPlaces(max_places, *, message=None, code=None)` — caps the digits after the decimal point. Accepts `int`, `float`, `decimal.Decimal`, and numeric strings. Trailing zeros count as places (so `Decimal("1.50")` reports 2 places).

```python
price: Annotated[Decimal, DecimalPlaces(max_places=2)]
```

#### `Even` · `Odd`

Integer parity checks. Reject `bool` and non-integer numerics.

```python
batch: Annotated[int, Even]
seat:  Annotated[int, Odd]
```

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

#### `NonNegative` · `Positive` · `Negative`

Pre-instantiated `Interval` shortcuts: `ge=0`, `gt=0`, and `lt=0` respectively. Use bare.

```python
score:   Annotated[int, NonNegative]
amount:  Annotated[float, Positive]
delta:   Annotated[float, Negative]
```

#### `NonZero`
`NonZero(*, message=None, code=None)` — rejects values equal to zero. Works with any numeric that supports `==`.

```python
divisor: Annotated[float, NonZero]
```

#### `Port`
`Port(*, message=None, code=None)` — integer in `[1, 65535]`.

```python
db_port: Annotated[int, Port]
```

#### `PowerOfTwo`
`PowerOfTwo(*, message=None, code=None)` — positive integer that is a power of two (1, 2, 4, 8, 16, …). Common for ML batch sizes, ring buffers, and cache-aligned allocations.

```python
batch_size: Annotated[int, PowerOfTwo]
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

When `choices` is an `enum.Enum` subclass, `OneOf` accepts both member instances **and** their underlying values:

```python
class Role(enum.Enum):
    ADMIN  = "admin"
    EDITOR = "editor"

# Either Role.ADMIN or "admin" passes.
role: Annotated[str | Role, OneOf(Role)]
```

```python
role: Annotated[str, OneOf(["admin", "editor", "viewer"])]
```

---

### Collections

#### `AllEqual`
`AllEqual(*, message=None, code=None)` — every element in the iterable must equal the others. Empty iterables pass. Rejects exhaustible iterators.

```python
all_same: Annotated[list[int], AllEqual]
```

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

#### `NonEmpty`

Pre-instantiated alias for `Len(min_len=1)`. Works on any sized container (string, list, dict, set, tuple). Use bare.

```python
tags: Annotated[list[str], NonEmpty]
name: Annotated[str, NonEmpty]
```


```python
class AddressDict(TypedDict):
    city: str

address: Annotated[AddressDict, Nested(AddressDict)]
```

#### `Sorted`
`Sorted(reverse=False, *, message=None, code=None)` — iterable items must be in non-decreasing order (or non-increasing when `reverse=True`). Equal neighbors are allowed. Rejects exhaustible iterators — convert to a `list`/`tuple` first.

```python
timestamps: Annotated[list[int], Sorted]
leaderboard: Annotated[list[int], Sorted(reverse=True)]
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

#### `IsTzAware` · `IsTzNaive`

Predicate-backed timezone-awareness checks for `datetime` instances. `IsTzAware` requires `tzinfo` set to any zone (use `IsUTC` to require UTC specifically); `IsTzNaive` requires no `tzinfo`.

```python
expires_at: Annotated[datetime.datetime, IsTzAware]
local_time: Annotated[datetime.datetime, IsTzNaive]
```

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
class StartsWithVowel:
    message: str | None = None

    def validate(self, value: str) -> None:
        if not value or value[0].lower() not in "aeiou":
            raise ValueError("Must start with a vowel.")
```

Full guide: **[Customization](advanced/customization.md)**.

---

## Next Steps

- **[Cross-Field Validation](advanced/cross_field.md)** — `Ref` and the `__monk_validate__` hook.
- **[Customization](advanced/customization.md)** — building reusable constraints in 3 lines.
- **[Settings & Type Metadata](advanced/settings.md)** — wrappers, sentinels, env vars for framework integration.
