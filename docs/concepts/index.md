# Core Concepts

`iron-monk` rests on a small philosophy and four pillars built on top of it. Read this page top-to-bottom for the *why*; click into each pillar for the deep-dive.

---

## Philosophy

Most validation libraries do too much. They coerce `"123"` into `123`, force you to inherit from a base class, and crash on the first error so you debug your payload one field at a time.

`iron-monk` flips all three:

- **Zero coercion.** If a string is not the right format, that is an error. Your data is never silently rewritten.
- **Zero base classes.** A `@monk` class is still a plain Python `dataclass`. No `BaseModel`, no metaclass tricks, no IDE slowdown.
- **Zero fail-fast.** Every field is checked. You get *every* error in one shot — no playing whack-a-mole.
- **Annotation is the schema.** Constraints live inside `typing.Annotated`. There is no separate model layer to keep in sync with your types.

Each pillar below reflects one of these choices.

---

## The Four Pillars

<div class="grid cards" markdown>

-   **1 · [The `@monk` Decorator](decorator.md)**

    ---

    One decorator. Three surfaces — classes, functions, methods. On classes it returns a regular `dataclass`; the rest of your code does not need to know `monk` exists.

-   **2 · [Constraints](constraints.md)**

    ---

    Plain classes with a single `validate(value) -> None` method. Stack them inside `typing.Annotated`. Compose with `AnyOf`, `Each`, `Ref`. Define your own in three lines.

-   **3 · [Validation](validation.md)**

    ---

    Three entry points matched to data shape: `validate()` for instances, `validate_dict()` for raw dicts, `validate_stream()` for iterables. Plus `validate_value()` for one-shot inline checks.

-   **4 · [Errors](errors.md)**

    ---

    Aggregated, not fail-fast. Three bad fields → three errors in one `ValidationError`. Includes `.flatten()` and `.to_rfc7807()` for HTTP APIs.

</div>

---

## Reading order

If this is your first time:

1. **[The Decorator](decorator.md)** — bind `@monk` to a class or function.
2. **[Constraints](constraints.md)** — write business rules with `Annotated`.
3. **[Validation](validation.md)** — pick the entry point that matches your data.
4. **[Errors](errors.md)** — collect every failure in one shot.

Each pillar is short (~50-100 lines) and self-contained. Skip ahead if a topic is already familiar.

---

## Next Steps

- **[Constraints Toolkit](../constraints/index.md)** — every built-in constraint with examples.
- **[Cross-Field Validation](../advanced/cross_field.md)** — `Ref` and the `__monk_validate__` hook.
- **[Customization](../advanced/customization.md)** — defining your own constraints in three lines.
- **[Settings & Type Metadata](../advanced/settings.md)** — unwrappers, type-keyed metadata, env vars for framework integration.
