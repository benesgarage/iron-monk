# 3 · Validation

Three entry points. Pick the one matching the data shape, not the framework.

## Why

Different stages of an application care about different shapes. Inside a service, you have objects. At an HTTP boundary, you have raw dicts. In a data pipeline, you have streams. Forcing all three to go through one entry point would mean instantiating objects you do not need or losing laziness.

## How

| Function | Input | When to use |
| --- | --- | --- |
| `validate(instance)` | A `@monk` class instance | Validate DTOs you have already built. Returns the (now-unlocked) instance for inline use. |
| `validate_value(value, *constraints)` | A single value + one or more constraints | Ad-hoc validation outside a `@monk` class — controllers, scripts, one-shot checks. |
| `validate_dict(data, schema)` | A raw `dict` + `TypedDict` / `@monk` class | High-throughput APIs that never instantiate objects. Supports `partial=True` (PATCH) and `drop_extra_keys=True` (sanitization). |
| `validate_stream(iterable, constraints)` | A generator / iterator | Lazy validation of large streams. The async sibling is `validate_async_stream`. |

```python
from monk import validate, validate_value, validate_dict, validate_stream

# Object: deferred until called explicitly
user = User(email="kai@example.com", age=30)
validate(user)

# Single value: skip the dataclass
validate_value(uploaded_body, MagicBytes(allowed=("image/png",)), FileSize(max_size=5_000_000))

# Dict: skip instantiation entirely
validate_dict({"email": "kai@example.com", "age": 30}, User)

# Stream: validate items as they are pulled
for item in validate_stream(big_generator, [Interval(gt=0)]):
    process(item)
```

## Gotchas

- **`validate(instance)` is a no-op for non-monk classes.** It raises `TypeError` to surface accidental misuse rather than silently passing.
- **`validate_value` aggregates failures.** Every constraint runs, and all per-constraint errors land in a single `ValidationError`. Matches `validate()` semantics — not fail-fast.
- **`validate_dict` does not allocate the object.** Side effects in `__post_init__` will *not* fire — that is by design. Use `validate(MyClass(**data))` if you need them.
- **Streams are exhausted.** `validate_stream` yields each validated item; consume the generator.

For execution-time flags (partial, drop-extra-keys, recursive nesting) see **[Advanced → Execution Models](../advanced/execution.md)**.

---

**Next:** [Pillar 4 — Errors](errors.md)
