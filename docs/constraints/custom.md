# Custom Messages & Constraints

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

Full guide: **[Customization](../advanced/customization.md)**.

---

## Next Steps

- **[Cross-Field Validation](../advanced/cross_field.md)** — `Ref` and the `__monk_validate__` hook.
- **[Customization](../advanced/customization.md)** — building reusable constraints in 3 lines.
- **[Settings & Type Metadata](../advanced/settings.md)** — wrappers, sentinels, env vars for framework integration.
