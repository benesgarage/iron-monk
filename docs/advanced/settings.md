# Settings and Type Metadata

`iron-monk` exposes a small set of process-wide knobs through the `settings` singleton and a handful of environment variables. Most apps never touch them. Reach for these when you are integrating with a framework that wraps values, uses sentinels, or expresses optionality through a custom generic.

```python
from monk import settings
```

---

## `settings.defer`

| Type | Default | Env var |
| --- | --- | --- |
| `bool` | `True` | `MONK_DEFER` |

Controls whether `@monk` classes validate eagerly inside `__post_init__` (`False`) or lazily on `validate(instance)` (`True`).

```python
settings.defer = False
```

```bash
export MONK_DEFER=false
```

You can override per class with `@monk(defer=False)` regardless of the global default. Function-mode `@monk` always validates eagerly.

---

## `settings.default_allow_none`

| Type | Default | Env var |
| --- | --- | --- |
| `bool` | `False` | `MONK_DEFAULT_ALLOW_NONE` |

When `True`, fields default to *nullable* — `None` is allowed unless an explicit `NotNull` is supplied. Use this when you delegate required-field enforcement to a runtime type checker like `beartype`.

```python
settings.default_allow_none = True
```

```bash
export MONK_DEFAULT_ALLOW_NONE=true
```

---

## `settings.unwrappers` — Reading Through Wrapper Types

Some frameworks hand you values wrapped in a generic container — Strawberry's `Maybe[T]`, Tortoise's `Mapped[T]`, custom monad-style `Some[T]`. A constraint like `Email` will fail on the wrapper because the wrapper is not a string.

`settings.unwrappers` is a per-type extractor map. `iron-monk` reads through the wrapper to validate the inner value, but **leaves the wrapper itself untouched** on the model:

```python
from typing import Annotated, TypeVar, Generic
from monk import monk, validate, settings
from monk.constraints import Email

T = TypeVar("T")

class SomeWrapper(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value

settings.unwrappers = {
    SomeWrapper: lambda x: x.value,
}

@monk
class UpdateRequest:
    email: SomeWrapper[Annotated[str, Email]]

req = validate(UpdateRequest(email=SomeWrapper("test@domain.com")))

assert isinstance(req.email, SomeWrapper)        # wrapper preserved
assert req.email.value == "test@domain.com"
```

Unwrapping is keyed by `type(value)` — exact match, no MRO walk. Register every concrete wrapper class your framework hands you.

---

## `settings.type_metadata` — Globally-Attached Constraints

`settings.type_metadata` lets you bind constraints to a generic type so they apply automatically anywhere that type appears. Useful for marking framework wrappers as nullable (e.g. Strawberry's `Maybe[T]` always means "this field can be missing").

```python
import strawberry
from monk import settings
from monk.constraints import Nullable

settings.type_metadata = {
    strawberry.Maybe: [Nullable],
}
```

Now any `Maybe[T]` annotation behaves as if the user had written `Annotated[T, Nullable]` themselves. Combine with `unwrappers` so the engine reads through the wrapper to validate the inner value while the metadata controls nullability.

The lookup is exact: `iron-monk` matches by `get_origin(hint) or hint`, so register the bare generic class (e.g. `strawberry.Maybe`, not `strawberry.Maybe[int]`).

---

## When to use which

| Goal | Tool |
| --- | --- |
| Run validation immediately on construction. | `defer=False` (per-class) or `MONK_DEFER=false` (global). |
| Let `beartype` own required-field enforcement. | `MONK_DEFAULT_ALLOW_NONE=true`. |
| A framework hands you wrapper objects but you want to validate inner values. | `settings.unwrappers`. |
| A custom generic always implies a constraint (e.g. `Maybe[T]` is always nullable). | `settings.type_metadata`. |

For concrete recipes per framework, see the **[Integrations](../examples/index.md)** section.
