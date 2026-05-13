# Nullability

Constraints are **required by default**. Two markers control optionality.

## `Nullable`

`Nullable()` — marker that allows `None`. Required inside `Each(...)` since `Each` evaluates its constraints functionally.

## `NotNull`

`NotNull(*, message=None, code=None)` — marker that forbids `None` and lets you customize the missing-value error message or code.

For top-level fields, prefer the standard `T | None` syntax — `iron-monk` natively intercepts `Union` and bypasses validation for missing data. Full discussion in **[Core Concepts → Nullability](../concepts/constraints.md#nullability)**.
