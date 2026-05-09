<div align="center">
  <a href="https://github.com/benesgarage/iron-monk">
    <img src="./docs/assets/monk.png" width="400" alt="iron-monk logo" style="display: block; margin-bottom: 0; padding-bottom: 0;">
  </a>
  <h1 style="margin-top: 0; padding-top: 0;">iron-monk</h1>
  <h4>Business constraint validation for people who hate data mutation.</h4>
  <h5><i>The fastest Pure-Python validator. 0 Dependencies. 100% Type-Safe.</i></h5>

  <p>
    <a href="https://pypi.org/project/iron-monk/"><img src="https://img.shields.io/pypi/v/iron-monk.svg?color=black" alt="PyPI version"></a>
    <a href="https://pypi.org/project/iron-monk/"><img src="https://img.shields.io/pypi/pyversions/iron-monk.svg?color=black" alt="Python Versions"></a>
    <a href="https://github.com/benesgarage/iron-monk/actions"><img src="https://img.shields.io/github/actions/workflow/status/benesgarage/iron-monk/ci.yml?branch=main&label=CI" alt="CI/CD"></a>
    <img src="https://img.shields.io/badge/Coverage-100%25-brightgreen.svg?color=black" alt="Coverage: 100%">
    <img src="https://img.shields.io/badge/Dependencies-0-success.svg?color=black" alt="Zero Dependencies">
    <a href="https://github.com/benesgarage/iron-monk/blob/main/LICENSE"><img src="https://img.shields.io/github/license/benesgarage/iron-monk?color=black" alt="License"></a>
  </p>
</div>

---

**📖 Read the official documentation here: [benesgarage.github.io/iron-monk](https://benesgarage.github.io/iron-monk/)**

---

## Installation

Install via your preferred package manager:

```bash
# Using pip
pip install iron-monk

# Using uv
uv add iron-monk

# Using poetry
poetry add iron-monk
```
> `iron-monk` uses the `monk` namespace. Always `import monk` in your code.

## Quickstart

```python
from typing import Annotated
from monk import monk, validate
from monk.constraints import Email, Interval, Len

@monk
class User:
    # No base class, no magic. Just your data.
    email: Annotated[str, Email]
    age:   Annotated[int, Interval(ge=18)]
    tags:  list[Annotated[str, Len(min_len=2)]]   # auto per-element validation

user = User(email="not-an-email", age=12, tags=["a"])
validate(user)  # Aggregates ALL THREE errors. Never fails fast.
```

When validation fails, `iron-monk` returns every failure in one structured response:

```python
from monk.exceptions import ValidationError

try:
    validate(user)
except ValidationError as e:
    print(e.errors)
    # [{'field': 'email', 'message': 'Must be a valid email address.', 'code': 'Email'},
    #  {'field': 'age',   'message': 'Must be greater than or equal to 18.', 'code': 'Interval'},
    #  {'field': 'tags[0]', 'message': 'Must have a minimum length of 2.',   'code': 'Len'}]

    print(e.flatten())          # → list[str] for logs
    print(e.to_rfc7807())       # → RFC 7807 problem-detail dict for HTTP APIs
```

### Custom constraints in 3 lines

```python
from monk import constraint

@constraint
class DivisibleBy:
    divisor: int

    def validate(self, value: int) -> None:
        if value % self.divisor != 0:
            raise ValueError(f"Must be divisible by {self.divisor}.")
```

## The Toolkit

A comprehensive suite of 60+ built-in constraints — including the kind most libraries punt on:

- **`CSV`** — validate comma-separated strings in place, no list allocation
- **`Cron`** — POSIX and AWS EventBridge scheduling strings
- **`Hash` / `CreditCard` / `ISBN`** — checksum-verified identifiers, zero third-party deps
- **`Ref` + `When` / `Switch`** — declarative cross-field validation that resolves at runtime
- **PATCH semantics** — `validate_dict(payload, Schema, partial=True)` for incremental updates
- **`Not` / `AnyOf` / `AllOf`** — invert and compose any constraint into richer rules

Plus the usual suspects (`Email`, `URL`, `UUID`, `JWT`, `Slug`, `IPAddress`, …) and string/numeric/datetime/path guards.

👉 [**Browse the full catalog &rarr;**](https://benesgarage.github.io/iron-monk/constraints/)

 ## Performance
 `iron-monk` doesn't compromise on speed.
 
 *Tested on Python 3.14.4, primarily executing 100,000 simple primitive validations.*

| Metric                            | `iron-monk`<br>*(v0.26.0)* | `msgspec`<br>*(v0.21.1)* | `pydantic`<br>*(v2.13.4)* | `attrs`<br>*(v26.1.0)* | `marshmallow`<br>*(v4.3.0)* |
|-----------------------------------|----------------------------|--------------------------|---------------------------|------------------------|------------------------------|
| **Package Size**                  | **`0.10 MB`**              | `0.44 MB`                | `5.88 MB`                 | `0.21 MB`              | `0.17 MB`                   |
| **Cold Start**                    | **`39.46ms`**              | `43.40ms`                | `75.17ms`                 | `50.59ms`              | `61.94ms`                   |
| **Object (100k)**                 | `0.158s`                   | `0.013s`                 | `0.054s`                  | `0.086s`               | N/A                          |
| **Dict (100k)**                   | `0.095s`                   | `0.058s`                 | `0.051s`                  | N/A                    | `0.440s`                     |
| **Nested Dict (100k)**            | `0.324s`                   | `0.071s`                 | `0.056s`                  | N/A                    | `1.403s`                     |
| **Invalid Dict (100k)**           | `0.235s`                   | `0.082s`                 | `0.075s`                  | N/A                    | `1.017s`                     |
| **Sanitized Dict (100k)**         | `0.104s`                   | `0.060s`                 | `0.050s`                  | N/A                    | `0.429s`                     |
| **Partial Dict (100k)**           | **`0.065s`**               | N/A                      | N/A                       | N/A                    | `0.267s`                     |
| **Union Dict (100k)**             | `0.119s`                   | `0.056s`                 | `0.033s`                  | N/A                    | N/A                          |
| **Large List (10k × 1k items)**   | `1.085s`                   | `0.056s`                 | `0.185s`                  | N/A                    | N/A                          |
| **Refs / Cross-Field (100k)**     | **`0.235s`**               | N/A                      | N/A                       | N/A                    | N/A                          |
| **Guard Access (1M attr reads)**  | `0.257s` *(plain dataclass: `0.025s`)* | N/A          | N/A                       | N/A                    | N/A                          |
| **Function Call (100k)**          | `0.171s`                   | N/A                      | `0.050s`                  | N/A                    | N/A                          |

**The Takeaway:** Rust-backed libraries win on raw loop speed, but `iron-monk` is the most efficient choice for the modern cloud. Faster cold starts, zero dependencies, and the only entry on the board that natively handles `PATCH` updates, payload sanitization, and standalone constraint execution make it the best-in-class validator for AWS Lambda, serverless environments, and CI/CD pipelines where install time and the network round trip are the real bottlenecks.

👉 [**See our benchmarking methodology &rarr;**](https://benesgarage.github.io/iron-monk/benchmarks/)

## Why iron-monk

Most validation libraries do too much — they coerce, force you to inherit from a base class, and stop at the first error. `iron-monk` flips all three.

- **Zero coercion**: `"123"` is never silently rewritten to `123`. Wrong format = error.
- **Zero base classes**: a `@monk` class is a plain `dataclass`. No `BaseModel`, no metaclass.
- **Zero fail-fast**: every field is checked. Get every error in one shot.
- **Annotation is the schema**: constraints live inside `typing.Annotated`. No model layer to keep in sync.

## Integrations

`iron-monk` drops into any modern Python project. Battle-tested recipes for:

- **Strawberry GraphQL** — `errors-as-data` for inputs, `Maybe[T]` integration
- **Starlette (ASGI)** — RFC 7807 exception handlers, dict-mode and DTO-mode handlers
- **SQLAlchemy 2.0 / Tortoise ORM** — DTO pattern at the API boundary
- **tyro** — validate dataclass-driven CLIs
- **beartype** — stack runtime type-checking under business constraints
- **App configuration** — fail-fast environment-variable validation on boot

👉 [**See the recipes &rarr;**](https://benesgarage.github.io/iron-monk/examples/)

## Feedback

PRs are not currently being accepted (see [CONTRIBUTING.md](./CONTRIBUTING.md)), but bug reports, feature requests, and integration use cases are welcome.

👉 [**Open an issue &rarr;**](https://github.com/benesgarage/iron-monk/issues)

## License

MIT