<div align="center">
  <a href="https://github.com/benesgarage/iron-monk">
    <img src="./assets/monk.png" width="400" alt="iron-monk logo" style="display: block; margin-bottom: 0; padding-bottom: 0;">
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


## Installation

```bash
pip install iron-monk
uv add iron-monk
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
- 🎯 **Do one thing well**. Unlike libraries that parse, coerce, and serialize, `iron-monk` focuses *strictly* on validation.
- 🪶 **Zero Dependencies**: Pure Python, 0 dependencies.
- 🧬 **Zero Inheritance**: No massive base classes polluting your namespace, just decorate a class with `@monk`. 
- 🛡️ **Strict**: We don't secretly coerce the string `"123"` into the integer `123`.
- ⏳ **Deferred Validation**: `iron-monk` captures data in a guarded state, giving *you* control over when validation occurs.

## Real-world examples
`iron-monk` is designed to drop into any modern Python project. Some notable projects include:
- 🍓 [Strawberry GraphQL](https://github.com/strawberry-graphql/strawberry): `iron-monk` helps validate `input` objects seamlessly. 
- ⚡ [Starlette (ASGI)](https://github.com/Kludex/starlette): HTTP endpoints with simple request validation using `iron-monk`. 
- 🖥️ [tyro (CLI tool)](https://github.com/brentyi/tyro): Generate command-line interfaces from dataclasses and validate with `iron-monk`.

> See `iron-monk` integrate with these projects, and more, [here](docs/examples.md)!

## The Toolkit
**Batteries included**. `iron-monk` comes with a suite of built-in constraints:

```python
from typing import Annotated
from monk import monk
from monk.constraints import Each, LowerCase, Len, Interval

@monk
class ComplexModel:
    # Validate every item in an iterable
    tags: Annotated[list[str], Each(LowerCase, Len(min_len=3))]
    
    # Custom error messages with dynamic interpolation
    age: Annotated[int, Interval(ge=18, message="You are {value}, but must be at least {ge}!")]
    
    # Infinitely nestable models with perfectly resolved dot-notation error paths
    configs: list[ServerConfig] 
```

> You can see the full list of constraints [here](docs/constraints.md)

## Advanced Usage
`iron-monk` provides powerful tools for complex validation scenarios. Check out the Advanced Usage guide to learn about:

- [🔄 **The Lifecycle**](docs/advanced.md#the-lifecycle): Understand the Guarded state of a `monk` object.
- [⚡ **Fail-Fast Mode**](docs/advanced.md#fail-fast-mode): Prefer to crash instantly? Enable Fail-Fast mode globally or per-class.
- [💬 **Custom Error Messages**](docs/advanced.md#custom-error-messages): Override default error strings with dynamic interpolation.
- [🤝 **Cross-Field Validation**](docs/advanced.md#model-level-cross-field-validation): Validate multiple fields together natively.
- [🛠️ **Custom Constraints**](docs/advanced.md#custom-constraints): Build your own rules using pure duck-typing and standard exceptions.

## License
MIT