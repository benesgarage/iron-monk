# Context-Aware Validation

Sometimes a rule depends on data that is **not on the model** — the logged-in user, a tenant configuration, the current time, a feature flag. Hard-coding such values into a constraint is wrong; reading them from a global is worse. `iron-monk` solves this with an explicit, read-only **context mapping**: you pass it to `validate()` (or `validate_dict()`), and constraints reach into it through a `Ctx(...)` marker.

`Ctx` is the twin of [`Ref`](cross_field.md): same compilation pipeline, same blueprint clone-per-call semantics, same zero-coercion guarantees. The only difference is *where the value comes from* — sibling field for `Ref`, context mapping for `Ctx`.

---

## `Ctx` — Pulling Values from Context

```python
from typing import Annotated
from monk import monk, validate
from monk.constraints import Interval, Ctx

@monk
class AgeGate:
    age: Annotated[int, Interval(ge=Ctx("min_age"))]

validate(AgeGate(age=21), context={"min_age": 18})  # passes
validate(AgeGate(age=15), context={"min_age": 18})  # raises ValidationError
```

The context is supplied at the call site, so the **same model** can be validated against different policies in different requests:

```python
admin_ctx = {"min_age": 13}
public_ctx = {"min_age": 18}

validate(AgeGate(age=15), context=admin_ctx)   # passes
validate(AgeGate(age=15), context=public_ctx)  # raises
```

`Ctx` works anywhere `Ref` works — inside `Interval`, `Eq`, `Len`, `OneOf`, `Subset`, `ContainsKeys`, `MultipleOf`, `StartsWith`, `EndsWith`, `ExactLen`, `AnyOf`, `Not`, `Each`, `DictOf`, etc. You can mix `Ref` and `Ctx` on the same field freely:

```python
from monk.constraints import Interval, Ref, Ctx

@monk
class Bid:
    floor: int
    offer: Annotated[int, Interval(gt=Ref("floor"), le=Ctx("ceiling"))]

validate(Bid(floor=10, offer=50), context={"ceiling": 100})
```

`Ref("floor")` is resolved from the sibling field; `Ctx("ceiling")` is resolved from the call-site mapping.

---

## `validate_dict` Supports Context Too

Schema-only validation (no instantiation) takes the same `context=` kwarg:

```python
from monk import monk, validate_dict
from monk.constraints import Eq, Ctx

@monk
class PostSchema:
    author_id: Annotated[int, Eq(Ctx("user_id"))]
    title: str

validate_dict({"author_id": 5, "title": "Hi"}, PostSchema, context={"user_id": 5})
```

---

## `__monk_validate__` Receives Context

The model-level hook automatically receives the context **iff its signature accepts a second positional argument**. The arity is detected once at decoration time, so the hot path is a single attribute read.

```python
from monk import monk, validate

@monk
class Post:
    author_id: int
    body: str

    def __monk_validate__(self, context):
        if self.author_id != context["user_id"]:
            yield ("author_id", "Author must match logged-in user.")

validate(Post(author_id=5, body="..."), context={"user_id": 5})  # passes
```

A hook that does not declare the parameter still works exactly as before — `iron-monk` will not pass it:

```python
@monk
class Old:
    name: str

    def __monk_validate__(self):  # legacy signature, untouched
        ...
```

---

## Errors

There are two failure modes specific to context-aware validation:

| Situation | Outcome |
| --- | --- |
| `Ctx("k")` is referenced but `context=` was **not provided** at the call site. | `MissingContextError` is raised — programmer error, surfaced eagerly. |
| `Ctx("k")` is referenced and `context=` was provided, but `"k"` is **missing** from the mapping. | A normal `ValidationError` is raised, aggregated alongside other field errors, with `code="MissingContextKey"`. |

The split is intentional: forgetting to pass context entirely is a wiring bug you want loud and immediate, whereas a missing key inside a partial context is a runtime data condition that belongs in the same error envelope as everything else the user typed wrong.

```python
from monk import validate
from monk.exceptions import ValidationError, MissingContextError

# 1. Programmer error
try:
    validate(AgeGate(age=21))
except MissingContextError:
    ...  # context= was never threaded through

# 2. Data condition — normal aggregation
try:
    validate(AgeGate(age=21), context={})
except ValidationError as e:
    assert e.errors[0]["code"] == "MissingContextKey"
```

---

## Nested `@monk` Models

Context is forwarded automatically when validation recurses into nested `@monk`-decorated values, so the inner model sees the same context the outer call passed in:

```python
from typing import Annotated
from monk import monk, validate
from monk.constraints import Interval, Ctx

@monk
class Inner:
    n: Annotated[int, Interval(ge=Ctx("min"))]

@monk
class Outer:
    inner: Inner

validate(Outer(inner=Inner(n=10)), context={"min": 5})  # forwarded into Inner
```

---

## Scope and Non-Goals

`Ctx` deliberately does **not** support:

- **`@monk`-wrapped functions.** Function arguments are already explicit. Use a regular argument plus `Ref("other_arg")` if you need cross-argument coupling.
- **Streams.** `validate_stream` and `validate_async_stream` operate on isolated items without sibling context.
- **Thread-local or implicit context.** All context flows through explicit kwargs. There is no `set_context()` API.
- **I/O inside constraints.** `Ctx` resolves a value from the mapping you already prepared. It will not call your database or fetch a feature flag for you. If you need that, prepare the snapshot at the boundary of your request and pass it in.

These are firm lines: they keep `iron-monk` predictable, framework-free, and easy to audit.

---

## When to Prefer Which

- **`Ref`** — the value lives on the **same instance** being validated.
- **`Ctx`** — the value lives **outside the model** (request, session, tenant, feature flags, clock).
- **`__monk_validate__(self, context)`** — the rule does not fit a constraint at all and needs Python control flow over both fields and context.
