<div align="center">
  <a href="https://github.com/benesgarage/iron-monk">
    <img src="./docs/assets/monk.png" width="400" alt="iron-monk logo" style="display: block; margin-bottom: 0; padding-bottom: 0;">
  </a>
  <h1 style="margin-top: 0; padding-top: 0;">iron-monk</h1>
  <h4>A minimalist, strict validation library for Python dataclasses.</h4>
</div>

[![CI/CD](https://img.shields.io/github/actions/workflow/status/benesgarage/iron-monk/ci.yml?branch=main&label=CI)](https://github.com/benesgarage/iron-monk/actions)
[![PyPI version](https://img.shields.io/pypi/v/iron-monk.svg?color=black)](https://pypi.org/project/iron-monk/)
[![Python Versions](https://img.shields.io/pypi/pyversions/iron-monk.svg?color=black)](https://pypi.org/project/iron-monk/)
[![License](https://img.shields.io/github/license/benesgarage/iron-monk?color=black)](https://github.com/benesgarage/iron-monk/blob/main/LICENSE)
[![Coverage: 100%](https://img.shields.io/badge/Coverage-100%25-brightgreen.svg?color=black)]()
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-0-success.svg?color=black)]()

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

Define your models using the `@monk` decorator and wrap your types in `Annotated` constraints.

```python
from typing import Annotated
from monk import monk, validate
from monk.constraints import Email, Interval
from monk.exceptions import ValidationError

@monk
class User:
    email: Annotated[str, Email]
    age: Annotated[int, Interval(ge=18)]

user = User(email="bad-email", age=12)

print(user.email) # Raises UnvalidatedAccessError

try:
    validate(user)
except ValidationError as e:
    print(e.errors) # [{'field': 'email', 'message': "..."}, {'field': 'age', 'message': "..."}]

user.email = "test@domain.com"
user.age = 25

validate(user)

print(user.email) # "test@domain.com"
```

## Core Philosophy

The Python ecosystem is dominated by heavy validation frameworks. `iron-monk` is built for a completely different philosophy:
- 🎯 **Do one thing well**: Unlike libraries that parse, coerce, and serialize, we focus strictly on validation.
- 🪶 **Zero Dependencies:** Pure Python. No compiled binaries or bloated environments.
- 🛡️ **No Magic:** We don't secretly coerce strings into integers. Strict types mean strict types.
- ⏳ **Deferred Validation:** Capture bad data in a guarded state instead of crashing instantly.
- 🧬 **Zero Inheritance:** No massive base classes polluting your namespace. Just a decorator.

## Real-world examples
`iron-monk` is designed to drop into any modern Python project. Some notable projects include:
- 🍓 Strawberry GraphQL: `iron-monk` helps validate `input` objects seamlessly. 
- ⚡ Starlette (ASGI): HTTP endpoints with simple request validation using `iron-monk`. 
- 🖥️ tyro (CLI tool): Generate command-line interfaces from dataclasses and validate with `iron-monk`.

👉 [**See `iron-monk` integrate with these projects, and more, in our Real-World Examples &rarr;**](https://benesgarage.github.io/iron-monk/examples/)

## The Toolkit
**Batteries included**. `iron-monk` comes with a comprehensive suite of built-in constraints. From networking (`Email`, `URL`, `IPAddress`) to collections (`Each`, `Unique`) and logic (`Not`, `Predicate`), you will rarely need to write your own rules.

👉 [**Check out the Constraint Toolkit &rarr;**](https://benesgarage.github.io/iron-monk/constraints/)

## Advanced Usage
Need to validate multiple fields together, override error messages with string interpolation, or instantly crash on bad data? `iron-monk` supports complex business logic while maintaining zero magic.

👉 [**Read the Advanced Usage Guide &rarr;**](https://benesgarage.github.io/iron-monk/advanced/)

## License
MIT