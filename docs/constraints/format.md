# Format & Identity

Format-style string validators that check structural correctness only. They never coerce.

!!! tip "Bytes are accepted too"
    These constraints also accept `bytes` and `bytearray` (decoded as UTF-8). See the [Strings page](strings.md) for the full bytes-handling note.

## `Base64`
`Base64(*, message=None, code=None)` — structurally validates a Base64 string.

## `DataURI`
`DataURI(*, message=None, code=None)` — RFC 2397 data URI (e.g., `data:image/png;base64,iVBOR...`). Structural only; does not decode the payload.

```python
embedded_image: Annotated[str, DataURI]
```

## `CreditCard`
`CreditCard(*, message=None, code=None)` — 13-19 digit string passing the Luhn checksum. Spaces and dashes are tolerated. Structural only — no issuer/network check.

```python
card_number: Annotated[str, CreditCard]
```

## `Email`
`Email(*, message=None, code=None)` — structural email check using the HTML5 living-standard atom regex. Local-part accepts the full RFC 5322 atom character set (``a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-``), matching the WHATWG `<input type="email">` validator. The domain must be a dotted hostname (at least one `.`), so single-label hosts like `user@localhost` are rejected. Quoted local parts and IP-literal domains (RFC 5321 §4.1.3) are intentionally out of scope; compose `AnyOf` with a custom `Match` if you need them.

```python
email: Annotated[str, Email]
```

## `Hash`
`Hash(algorithm, *, message=None, code=None)` — hex digest of fixed length per algorithm. Supported: `md5`, `sha1`, `sha224`, `sha256`, `sha384`, `sha512`, `blake2s`, `blake2b`. Algorithm name is case-insensitive.

```python
content_sha256: Annotated[str, Hash("sha256")]
```

## `HexColor`
`HexColor(*, message=None, code=None)` — `#RGB`, `#RGBA`, `#RRGGBB`, or `#RRGGBBAA`.

## `Hostname`
`Hostname(*, message=None, code=None)` — RFC 1123 hostname: each label 1-63 chars (alphanum + hyphen, no leading/trailing hyphen), total ≤253 chars. Single-label hostnames like `localhost` pass.

```python
host: Annotated[str, Hostname]
```

## `HttpURL`
`HttpURL(*, message=None, code=None)` — URL restricted to the `http` or `https` scheme. Use this when you specifically want to reject `ftp://`, `file://`, `javascript:`, etc.

```python
webhook_url: Annotated[str, HttpURL]
```

## `IPAddress`
`IPAddress(*, message=None, code=None)` — IPv4 or IPv6.

## `ISBN`
`ISBN(*, message=None, code=None)` — ISBN-10 or ISBN-13 with checksum verification. Spaces and dashes are tolerated; the trailing `X` check character is accepted for ISBN-10.

```python
book_isbn: Annotated[str, ISBN]
```

## `IsISO8601`
`IsISO8601(*, message=None, code=None)` — ISO 8601 date or datetime string. **Does not coerce** to a `datetime`.

## `JSON`
`JSON(*, message=None, code=None)` — accepts only strings that successfully parse as JSON. Does not return the parsed value.

## `JWT`
`JWT(*, message=None, code=None)` — JSON Web Token shape (`header.payload.signature`). Structural only — no signature verification.

## `MacAddress`
`MacAddress(*, message=None, code=None)` — `00:1A:2B:3C:4D:5E` or `-` separator.

## `MimeType`
`MimeType(*, message=None, code=None)` — RFC 6838 `type/subtype` with optional `; param=value` parameters. Validates the **string format** of a claimed mime header; for content sniffing of an actual file body, see [`MagicBytes`](uploads.md#magicbytes).

```python
content_type: Annotated[str, MimeType]
```

## `PEMBlock`
`PEMBlock(*, message=None, code=None)` — structurally validates a PEM-encoded block (X.509 cert, RSA/SSH key, etc.). Verifies the `-----BEGIN <LABEL>-----` / `-----END <LABEL>-----` envelope matches and the body contains Base64 content. **Performs no cryptographic verification** — use a crypto library for that.

```python
cert: Annotated[str, PEMBlock]
```

## `PhoneE164`
`PhoneE164(*, message=None, code=None)` — structural [E.164](https://en.wikipedia.org/wiki/E.164) phone number: leading `+`, 1-15 digits, no separators. Structural only — no carrier/region lookup.

```python
phone: Annotated[str, PhoneE164]
```

## `SemVer`
`SemVer(*, message=None, code=None)` — Semantic Versioning string.

## `Slug`
`Slug(*, message=None, code=None)` — URL-safe slug (lowercase alphanumerics and hyphens).

## `TimeOfDay`
`TimeOfDay(*, message=None, code=None)` — 24-hour `HH:MM` or `HH:MM:SS` time string. Does not validate full datetimes — see `IsISO8601` for that.

```python
opening_hour: Annotated[str, TimeOfDay]
```

## `TimezoneName`
`TimezoneName(*, message=None, code=None)` — IANA timezone name (e.g., `America/New_York`, `Europe/Berlin`, `UTC`). Resolved via `zoneinfo.ZoneInfo`; `zoneinfo` is imported lazily.

```python
display_tz: Annotated[str, TimezoneName]
```

## `URL`
`URL(*, message=None, code=None)` — scheme + netloc check.

## `UUID`
`UUID(*, message=None, code=None)` — UUID string or native `uuid.UUID`.

```python
import uuid
node_id: Annotated[str | uuid.UUID, UUID]
```
