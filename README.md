<div align="center">
  <a href="https://github.com/benesgarage/iron-monk">
    <img src="./docs/assets/monk.png" width="400" alt="iron-monk logo" style="display: block; margin-bottom: 0; padding-bottom: 0;">
  </a>
  <h1 style="margin-top: 0; padding-top: 0;">iron-monk</h1>
  <h4>A minimalist, zero-coercion validation library for Python.</h4>
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

`iron-monk` provides four ways to validate your data using standard Python type hints and explicit constraints.

```python
from typing import Annotated, TypedDict
from monk import monk, validate, validate_dict
from monk.constraints import Email, Interval

# 1. Dataclasses (Deferred Validation or Fail-Fast)
@monk
class User:
    email: Annotated[str, Email]
    age: Annotated[int, Interval(ge=18)]

user = User(email="bad-email", age=12)
validate(user) # ❌ Raises ValidationError

# 2. Functions (Instant Validation)
@monk
def send_invite(email: Annotated[str, Email]):
    print(f"Sending to {email}")

send_invite("bad-email") # ❌ Raises ValidationError instantly

# 3. Raw Dictionaries (Zero-Instantiation Validation)
class UserDict(TypedDict):
    email: Annotated[str, Email]

validate_dict({"email": "bad-email"}, UserDict) # ❌ Raises ValidationError

# 4. Direct Execution (Standalone Variables)
Email().validate("bad-email") # ❌ Raises standard ValueError instantly
```

When validation fails, `iron-monk` aggregates all errors so you can easily return structured JSON payloads to your frontend:
```python
from monk import validate
from monk.exceptions import ValidationError

try:
    validate(user)
except ValidationError as e:
    # Get a list of dictionaries for your JSON response
    print(e.errors) 
    # [{'field': 'email', 'message': 'Must be a valid email address.', 'code': 'Email'}, ...]
    
    # Or get a flat list of strings for quick logging
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

## Real-world examples
`iron-monk` is designed to drop into any modern Python project. Some notable projects include:
- 🍓 Strawberry GraphQL: `iron-monk` helps validate `input` objects seamlessly. 
- ⚡ Starlette (ASGI): HTTP endpoints with simple request validation using `iron-monk`. 
- 🖥️ tyro (CLI tool): Generate command-line interfaces from dataclasses and validate with `iron-monk`.

👉 [**See `iron-monk` integrate with these projects, and more, in our Real-World Examples &rarr;**](https://benesgarage.github.io/iron-monk/examples/)

## Core Concepts
Understand the validation lifecycle, how to cleanly extract error dictionaries, and how to enforce required fields.

👉 [**Read the Core Concepts Guide &rarr;**](https://benesgarage.github.io/iron-monk/core_concepts/)

## The Toolkit
**Batteries included**. `iron-monk` comes with a comprehensive suite of built-in constraints. From networking (`Email`, `URL`, `IPAddress`) to collections (`Each`, `Unique`) and logic (`Not`, `Predicate`), you will rarely need to write your own rules.

👉 [**Check out the Constraint Toolkit &rarr;**](https://benesgarage.github.io/iron-monk/constraints/)

## Advanced Usage
Need to validate multiple fields together, override error messages with string interpolation, or instantly crash on bad data? `iron-monk` supports complex business logic while maintaining zero magic.

👉 [**Read the Advanced Usage Guide &rarr;**](https://benesgarage.github.io/iron-monk/advanced/)

## License
MIT