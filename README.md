<div align="center">
  <a href="https://github.com/benesgarage/iron-monk">
    <img src="./docs/assets/monk.png" width="400" alt="iron-monk logo" style="display: block; margin-bottom: 0; padding-bottom: 0;">
  </a>
  <h1 style="margin-top: 0; padding-top: 0;">iron-monk</h1>
  <h4>A minimalist, zero-coercion validation library for Python.</h4>

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

## Quickstart

`iron-monk` provides four ways to validate your data using constraints.

```python
from typing import Annotated, TypedDict
from monk import monk, validate, validate_dict
from monk.constraints import Email, Interval

@monk
class User:
    email: Annotated[str, Email]
    age: Annotated[int, Interval(ge=18)]

user = User(email="bad-email", age=12)
validate(user) # ❌ ValidationError

@monk
def send_invite(email: Annotated[str, Email]):
    print(f"Sending to {email}")

send_invite("bad-email") # ❌ ValidationError

class UserDict(TypedDict):
    email: Annotated[str, Email]

validate_dict({"email": "bad-email"}, UserDict) # ❌ ValidationError

Email().validate("bad-email") # ❌ ValueError
```

When validation fails, `iron-monk` aggregates all errors into structured dictionaries.
```python
from monk import validate
from monk.exceptions import ValidationError

try:
    validate(user)
except ValidationError as e:
    print(e.errors) 
    # [{'field': 'email', 'message': 'Must be a valid email address.', 'code': 'Email'}, ...]
    print(e.flatten()) 
    # ['email: Must be a valid email address.', 'age: Must be greater than or equal to 18.']
```

## Core Philosophy

The Python ecosystem is dominated by heavy validation frameworks. `iron-monk` is built for a completely different philosophy:
- 🎯 **Do one thing well**: Unlike libraries that parse, coerce, and serialize, we focus on validation.
- 🪶 **Zero Dependencies:** Pure Python. No compiled binaries or bloated environments.
- 🛡️ **Zero Coercion**: We don't secretly cast the string "123" into the integer 123.
- 🤝 **Agnostic to Type Checking:** We enforce *business constraints*, not base Python types.
- ⏳ **Deferred Validation:** Capture bad data in a guarded state instead of crashing instantly.
- 🧬 **Zero Inheritance:** No massive base classes polluting your namespace. Just a decorator.

 ## Performance
 `iron-monk` doesn't compromise on speed.
 
 *Tested on Python 3.13, executing 100,000 simple primitive validations.*

| Metric                               | `iron-monk`<br>*(v0.18.0)* | `msgspec`<br>*(v0.18.6)* | `pydantic`<br>*(v2.10.6)* | `attrs`<br>*(v24.3.0)* | `marshmallow`<br>*(v3.26.1)* |
|--------------------------------------|----------------------------|--------------------------|---------------------------|------------------------|------------------------------|
| **Package Size**                     | `0.04 MB`                  | `0.44 MB`                | `5.91 MB`                 | `0.21 MB`              | `0.17 MB`                    | `0.09 MB` |
| **Cold Start**                       | `32.05ms`                  | `36.96ms`                | `61.59ms`                 | `38.78ms`              | `40.00ms`                    |
| **Object Validation (100k)**         | `0.170s`                   | `0.012s`                 | `0.054s`                  | `0.083s`               | N/A                          |
| **Dict Validation (100k)**           | `0.075s`                   | `0.055s`                 | `0.051s`                  | N/A                    | `0.410s`                     |
| **Nested Dict Validation (100k)**    | `0.388s`                   | `0.028s`                 | `0.131s`                  | N/A                    | `1.379s`                     |
| **Invalid Dict Validation (100k)**   | `0.234s`                   | `0.079s`                 | `0.077s`                  | N/A                    | `0.993s`                     |
| **Sanitized Dict Validation (100k)** | `0.087s`                   | `0.058s`                 | `0.052s`                  | N/A                    | `0.412s`                     |
| **Partial Dict Validation (100k)**   | `0.059s`                   | N/A                      | N/A                       | N/A                    | `0.276s`                     |
| **Function Validation (100k)**       | `0.155s`                   | N/A                      | `0.055s`                  | N/A                    | N/A                          |

**The Takeaway:** When evaluating features, execution speed, package size, and cold-start times together, `iron-monk` is holistically the best-in-class pure-Python validation framework.

👉 [**See our benchmarking methodology &rarr;**](https://benesgarage.github.io/iron-monk/benchmarks/)

## Real-world examples
`iron-monk` is designed to drop into any modern Python project. Some notable projects include:
- 🍓 Strawberry GraphQL: `iron-monk` helps validate `input` objects seamlessly. 
- ⚡ Starlette (ASGI): HTTP endpoints with simple request validation using `iron-monk`. 
- 🖥️ tyro (CLI tool): Generate command-line interfaces from dataclasses and validate with `iron-monk`.

👉 [**See `iron-monk` integrate with these projects, and more &rarr;**](https://benesgarage.github.io/iron-monk/examples/)

## Core Concepts
Understand the validation lifecycle, how to cleanly extract error dictionaries, and how to enforce required fields.

👉 [**Read the Core Concepts Guide &rarr;**](https://benesgarage.github.io/iron-monk/core_concepts/)

## The Toolkit
**Batteries included**. `iron-monk` comes with a comprehensive suite of built-in constraints. From networking (`Email`, `Port`, `MacAddress`) and formats (`HexColor`, `JSON`, `SemVer`) to collections (`Subset`, `ContainsKeys`) and logic (`Not`, `Predicate`), you will rarely need to write your own rules.

👉 [**Check out the Constraint Toolkit &rarr;**](https://benesgarage.github.io/iron-monk/constraints/)

## Advanced Usage
Need to validate multiple fields together, override error messages with string interpolation, or instantly crash on bad data? `iron-monk` supports complex business logic while maintaining zero magic.

👉 [**Read the Advanced Usage Guide &rarr;**](https://benesgarage.github.io/iron-monk/advanced/)

## License
MIT