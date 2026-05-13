# 1 · The `@monk` Decorator

The single entry point for binding constraints to your code. It adapts to what it wraps.

## Why

Most validators force you to choose an architecture: a `BaseModel` for objects, a `Schema` class for dicts, a `validator()` decorator for functions. `@monk` is one decorator that covers all three surfaces — and on classes, it returns a regular `dataclass`, so the rest of your code does not need to know `monk` exists.

## How

| Wraps | Effect |
| --- | --- |
| `class` | Becomes a `@dataclass`. Validation is **deferred** by default — you call `validate(instance)` explicitly. Attribute access is locked until then. |
| `def` / `async def` | Wraps the call. Arguments and return value are validated **eagerly** on every invocation. |
| Method | Same as a function. Always place `@monk` *below* `@classmethod` / `@staticmethod`. |

```python
from monk import monk

@monk                          # deferred — call validate(user) yourself
class User: ...

@monk(defer=False)             # eager — fails inside __post_init__
class StrictUser: ...

@monk
def process_user(...): ...     # eager — fails on every call
```

## Gotchas

- **Deferred is the default for classes.** Touching `user.email` before `validate(user)` raises `UnvalidatedAccessError`. This is intentional: it lets you pass DTOs through layers and validate at the boundary (e.g. just before a DB write).
- **Globals.** `MONK_DEFER=false` (env var) or `settings.defer = False` (code) flip the default for the whole process.
- **Decorator order matters on methods.** `@classmethod` / `@staticmethod` must wrap *outside* `@monk`, otherwise binding breaks.

---

**Next:** [Pillar 2 — Constraints](constraints.md)
