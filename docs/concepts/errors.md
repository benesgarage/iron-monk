# 4 · Errors

The unique selling point. Every other library on the JVM/Rust/Python market fails fast. `iron-monk` does not.

## Why

When a payload has three bad fields, your user wants to know all three at once, not one at a time as they fix each. Aggregation is the difference between a usable API and a frustrating one.

## How

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

## Gotchas

- **Standalone `Constraint.validate()` is *not* aggregated.** It raises native `ValueError` / `TypeError` because there is no field context to aggregate over. Aggregation is a property of `validate` / `validate_value` / `validate_dict` / function-mode `@monk`.
- **`to_rfc7807()` defaults to HTTP 400.** Pass `status=`, `title=`, `type_uri=`, `instance=` to customize per route.
- **Error codes are class names by default.** If you alias a constraint (`MyEmail = Email`), the code stays `"Email"`. To override, set `code="..."` on the constraint instance.

---

## Next Steps

- **[Constraints Toolkit](../constraints/index.md)** — every built-in constraint with examples.
- **[Cross-Field Validation](../advanced/cross_field.md)** — `Ref` and the `__monk_validate__` hook.
- **[Customization](../advanced/customization.md)** — defining your own constraints in three lines.
- **[Settings & Type Metadata](../advanced/settings.md)** — unwrappers, type-keyed metadata, env vars for framework integration.
