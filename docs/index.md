---
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

<img src="assets/monk.png" alt="iron-monk logo" class="hero-logo">

# iron-monk

**Business-constraint validation for people who hate data mutation.**

A pure-Python validator with zero dependencies, zero coercion, and zero base classes. Just a decorator.

[Get Started :material-arrow-right:](getting_started.md){ .md-button .md-button--primary }
[View on GitHub :material-github:](https://github.com/benesgarage/iron-monk){ .md-button }

</div>

---

## Why iron-monk

Most validation libraries do too much. They coerce your data, force you to inherit from a base class, and stop at the first error so you debug payloads one field at a time.

`iron-monk` flips all three.

<div class="grid cards" markdown>

-   :material-shield-lock-outline: **Zero coercion**

    `"123"` is never silently rewritten to `123`. If a string is the wrong format, that is an error.

-   :material-package-variant: **Zero dependencies**

    Pure Python. No compiled binaries, no install-time toolchain, no `pydantic_core` lurking in your container.

-   :material-format-list-bulleted-square: **Aggregate, don't fail-fast**

    Validation collects every error and reports them in a single `ValidationError`. No whack-a-mole.

-   :material-tag-text-outline: **Annotation is the schema**

    Constraints live inside `typing.Annotated`. No `BaseModel`, no `Schema` class, no metaclass.

</div>

---

## A 30-second tour

```python
from typing import Annotated
from monk import monk, validate
from monk.constraints import Email, Interval

@monk
class User:
    email: Annotated[str, Email]
    age:   Annotated[int, Interval(ge=18)]

user = User(email="bad-email", age=12)
validate(user)
# ValidationError aggregating BOTH the email and age failures
```

---

## Where to next

1. **[Getting Started](getting_started.md)** — installation, the validation lifecycle, error handling.
2. **[Core Concepts](concepts.md)** — the four pillars and the philosophy behind them.
3. **[Constraints](constraints.md)** — the full catalog of built-in rules.
4. **[Advanced Usage](advanced/index.md)** — cross-field rules, custom constraints, settings.
5. **[Integrations](examples/index.md)** — Strawberry, Starlette, SQLAlchemy, Tortoise, tyro, beartype.
