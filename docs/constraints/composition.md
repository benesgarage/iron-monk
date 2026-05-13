# Composition

`iron-monk` ships logical wrappers and per-element wrappers so any constraint can be lifted into a richer context.

## `AnyOf`

`AnyOf(*constraints, message=None, code=None)`

Passes if **at least one** wrapped constraint passes.

```python
from monk.constraints import AnyOf, Email, URL

contact: Annotated[str, AnyOf(Email, URL)]
```

## `AllOf`

`AllOf(*constraints, message=None, code=None)`

Passes only if **every** wrapped constraint passes. Equivalent to stacking them inside `Annotated`, but useful when you need to wrap a group as a single unit (e.g. inside `Not`, `AnyOf`, or `Each`).

```python
from monk.constraints import AllOf, LowerCase, Trimmed

name: Annotated[str, AllOf(LowerCase, Trimmed)]
```

## `Not`

`Not(constraint, *, message=None, code=None)`

Inverts a constraint. Fails when the wrapped constraint passes.

```python
from monk.constraints import Not, Email

not_an_email: Annotated[str, Not(Email)]
```

## `When`

`When(field, test, then, else_=None, *, message=None, code=None)`

Conditional validation. Resolves `field` (typically a `Ref` to a sibling field), runs `test` against it, and applies `then` to the **current** field's value when `test` passes. If `test` fails and `else_` is provided, `else_` is applied instead. See **[Cross-Field Validation](../advanced/cross_field.md)** for end-to-end examples.

```python
from monk.constraints import When, Eq, Len, Ref

cc_number: Annotated[str, When(field=Ref("payment_method"), test=Eq("credit"), then=Len(min_len=16, max_len=16))]
```

## `Switch`

`Switch(field, cases, default=None, *, message=None, code=None)`

Multi-branch dispatch. Resolves `field` (typically a `Ref`) and applies the constraint mapped to that value in `cases`. Falls back to `default` when the discriminator is missing or unhashable; raises a `ValidationError` if neither matches. Sugar for chained `When` over a discriminated union.

```python
from monk.constraints import Switch, Email, Match, Len, Ref

target: Annotated[str, Switch(
    field=Ref("channel"),
    cases={"email": Email, "sms": Match(r"^\+\d+$")},
    default=Len(min_len=1),
)]
```

## Per-Element Validation

Annotate the element type directly. `iron-monk` synthesizes per-element rules at decoration time for `list`, `set`, `frozenset`, `tuple`, and `dict`:

```python
from typing import Annotated
from monk.constraints import Email, Interval, Len

emails: list[Annotated[str, Email]]
ages:   list[Annotated[int, Interval(ge=0)]]
mixed:  list[Annotated[int, Interval(gt=0)] | Annotated[str, Len(min_len=1)] | None]
pair:   tuple[Annotated[int, Interval(gt=0)], Annotated[str, Len(min_len=1)]]   # heterogeneous
links:  dict[Annotated[str, LowerCase], Annotated[str, URL]]
```

Use `T | None` inside the element annotation to allow `None` items.

## `Each`

`Each(*constraints)`

The explicit form. Reach for it when:

- The container is untyped (`list`, `dict`, plain `Annotated[list, ...]`).
- You want to layer **extra** rules on top of an inner-annotated container — supplying an outer `Each` short-circuits auto-synthesis to avoid double validation.
- You need the constraint as a value (e.g. inside `Not`, `AnyOf`, or as an argument to a custom helper).

Pass `Nullable` to allow `None` items, or `NotNull` to forbid them with a custom message.

```python
from monk.constraints import Each, Email, Nullable

emails: Annotated[list, Each(Email, Nullable)]   # untyped list
```

## `DictOf`

`DictOf(*, key=None, value=None, message=None, code=None)`

The explicit form for dictionaries. Use it for untyped `dict` fields, or to layer extra rules on top of an annotated `dict[K, V]`. Either side accepts a single constraint or an iterable.

```python
from monk.constraints import DictOf, LowerCase, URL

links: Annotated[dict, DictOf(key=LowerCase, value=URL)]
```

## `Predicate`

`Predicate(func, *, message=None, code=None)`

Wraps any boolean-returning callable as a constraint. The fastest path to one-off rules.

```python
from monk.constraints import Predicate

def is_even(n: int) -> bool:
    return n % 2 == 0

batch_size: Annotated[int, Predicate(is_even)]
```
