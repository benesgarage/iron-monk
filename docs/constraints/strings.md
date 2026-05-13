# Strings

!!! tip "Bytes are accepted too"
    Every string-typed constraint in this section (and [Format & Identity](format.md)) accepts `bytes` and `bytearray` in addition to `str`. Inputs are decoded as UTF-8 before validation; invalid UTF-8 raises a `ValueError`. This lets you validate raw network/protobuf payloads without manually decoding first.

## `Blank`
`Blank(*, message=None, code=None)` — requires the value to be empty or contain only whitespace. Combine with `Not` (`Not(Blank)`) for the inverse.

```python
placeholder: Annotated[str, Blank]
```

## `EndsWith`
`EndsWith(suffix, *, message=None, code=None)` — requires the value to end with `suffix`. Accepts `Ref`.

```python
avatar: Annotated[str, EndsWith(".png")]
```

## `HexString`
`HexString(length=None, *, message=None, code=None)` — value contains only hexadecimal characters. If `length` is set, the string must match it exactly.

```python
session_token: Annotated[str, HexString(length=64)]
```

## `IsAlnum` · `IsAlpha` · `IsAscii` · `IsDigit` · `LowerCase` · `Printable` · `UpperCase`

Predicate-backed string property checks. No constructor — use the bare instance. `Printable` rejects control characters (`\x00-\x1f`, `\x7f`); empty strings pass.

```python
from monk.constraints import LowerCase, IsDigit, Printable
slug:        Annotated[str, LowerCase]
pin:         Annotated[str, IsDigit]
display:     Annotated[str, Printable]
```

## `Match`
`Match(pattern, *, message=None, code=None)` — requires the value to match a regex `pattern` (compiled once at construction).

```python
sku: Annotated[str, Match(r"^PROD-\d+$")]
```

## `MaxBytes`
`MaxBytes(max_bytes, *, message=None, code=None)` — UTF-8 encoded length must not exceed `max_bytes`. Accepts `str` (encoded to count) or raw `bytes` / `bytearray` (counted directly). Use for database column limits and API payload guards where character count diverges from byte count (CJK, emoji, accented Latin).

```python
bio: Annotated[str, MaxBytes(280)]
```

## `NoWhitespace`
`NoWhitespace(*, message=None, code=None)` — rejects strings containing any whitespace character (space, tab, newline, etc.).

```python
username: Annotated[str, NoWhitespace]
```

## `PathSafe`
`PathSafe(*, message=None, code=None)` — filename hardening: rejects path separators (`/`, `\`), null bytes, parent refs (`..`), the literal `.`/`..` filenames, and empty strings. Use for user-uploaded filenames, S3 key segments, traversal prevention.

```python
upload_name: Annotated[str, PathSafe]
```

## `SingleLine`
`SingleLine(*, message=None, code=None)` — rejects strings containing `\n` or `\r`. Tabs and other whitespace are allowed.

```python
log_message: Annotated[str, SingleLine]
```

## `StartsWith`
`StartsWith(prefix, *, message=None, code=None)` — requires the value to start with `prefix`. Accepts `Ref`.

```python
category: Annotated[str, StartsWith("cat_")]
```

## `Trimmed`
`Trimmed(*, message=None, code=None)` — rejects strings with leading or trailing whitespace.

```python
name: Annotated[str, Trimmed]
```
