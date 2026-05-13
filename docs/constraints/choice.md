# Equality & Choice

## `Eq`
`Eq(value, *, message=None, code=None)` — strict equality (`==`). Accepts `Ref`.

```python
status: Annotated[str, Eq("active")]
```

## `OneOf`
`OneOf(choices, *, message=None, code=None)` — value must be a member of `choices`. Accepts `Ref`.

When `choices` is an `enum.Enum` subclass, `OneOf` accepts both member instances **and** their underlying values:

```python
class Role(enum.Enum):
    ADMIN  = "admin"
    EDITOR = "editor"

# Either Role.ADMIN or "admin" passes.
role: Annotated[str | Role, OneOf(Role)]
```

```python
role: Annotated[str, OneOf(["admin", "editor", "viewer"])]
```
