# 2 · Constraints

The business rules themselves — `Email`, `Interval`, `Len`, etc.

## Why

A constraint is just a class with one method: `validate(value) -> None`. That is the entire protocol. Anything that satisfies it can be used as a constraint — no registry, no metaclass, no plugin system. The toolkit stays small and trivially extensible.

## How

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

Constraints also compose with logical wrappers (`AnyOf`, `AllOf`, `Not`) and per-element wrappers (`Each`, `DictOf`). See **[Constraints → Composition](../constraints/composition.md)**.

**Per-element rules go inside the element type.** `iron-monk` recognizes annotated element types inside `list`, `set`, `tuple`, and `dict` and validates each item automatically:

```python
items: list[Annotated[int, Interval(gt=0)]]
mixed: list[Annotated[int, Interval(gt=0)] | Annotated[str, Len(min_len=1)] | None]
pair:  tuple[Annotated[int, Interval(gt=0)], Annotated[str, Len(min_len=1)]]
links: dict[Annotated[str, LowerCase], Annotated[str, URL]]
```

Reach for the explicit `Each(...)` / `DictOf(...)` wrappers only when the container is untyped or you need to layer extra rules. See **[Constraints → Composition](../constraints/composition.md)**.

## Nullability

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

## Cross-field rules

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

`Ref` is resolved at validation time. See **[Cross-Field Validation](../advanced/cross_field.md)** for the full mechanic and the `__monk_validate__` hook.

## Custom constraints

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

See **[Customization](../advanced/customization.md)** for message templating, code overrides, and refs in custom constraints.

## Gotchas

- **Constraints never coerce.** `Annotated[int, Interval(gt=0)]` does *not* parse strings. Pass the right type or expect a `TypeError`.
- **Order matters when constraints share a domain.** `Len(min_len=3)` before `LowerCase` will fail length first, lower-case second. Stable, but worth knowing.
- **`Each` does not consume iterators.** Passing a generator raises — convert to a list/tuple first, or use `validate_stream` (see [Pillar 3](validation.md)).

---

**Next:** [Pillar 3 — Validation](validation.md)
