# Constraints

Every business rule in `iron-monk` is a **constraint**: a small class with a single `validate(value) -> None` method. Constraints are attached to type hints with `typing.Annotated`. They never coerce, never mutate, and never fail-fast — every error is collected.

This section is the catalog. For the design rationale, see **[Core Concepts](../concepts/index.md)**.

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

Most constraints also accept **`Ref(...)`** in place of literal values to reference sibling fields. See **[Cross-Field Validation](../advanced/cross_field.md)**.

---

## Catalog

Constraints are grouped by data domain:

- **[Composition](composition.md)** — `AnyOf`, `AllOf`, `Not`, `When`, `Switch`, `Each`, `DictOf`, `Predicate`, per-element validation.
- **[Nullability](nullability.md)** — `Nullable`, `NotNull`.
- **[Strings](strings.md)** — `Blank`, `EndsWith`, `HexString`, `LowerCase`, `Match`, `MaxBytes`, `PathSafe`, `Trimmed`, …
- **[Format & Identity](format.md)** — `Email`, `URL`, `JWT`, `UUID`, `JSON`, `Base64`, `MimeType`, `Hash`, `CreditCard`, `ISBN`, `PEMBlock`, …
- **[Numeric](numeric.md)** — `Interval`, `MultipleOf`, `Even`/`Odd`, `Positive`/`Negative`, `NonZero`, `Port`, `PowerOfTwo`, …
- **[Equality & Choice](choice.md)** — `Eq`, `OneOf`.
- **[Collections](collections.md)** — `Len`, `Unique`, `Contains`, `Sorted`, `Subset`, `CSV`, `Nested`, …
- **[Datetime & Schedule](datetime.md)** — `Future`, `Past`, `IsTzAware`, `IsUTC`, `Cron`, …
- **[Filesystem](filesystem.md)** — `IsFile`, `IsDir`.
- **[File Uploads](uploads.md)** — `FileSize`, `MagicBytes`.
- **[Geospatial](geospatial.md)** — `LatLong`.
- **[Custom Messages & Constraints](custom.md)** — `{placeholder}` formatting, the `@constraint` decorator.
