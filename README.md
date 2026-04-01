<div align="center">
  <a href="https://github.com/benesgarage/iron-monk">
    <img src="./docs/assets/monk.png" width="400" alt="iron-monk logo" style="display: block; margin-bottom: 0; padding-bottom: 0;">
  </a>
  <h1 style="margin-top: 0; padding-top: 0;">iron-monk</h1>
  <h4>Business constraint validation for people who hate data mutation.</h4>
  <h5><i>The fastest Pure-Python validator. 0.06MB. 0 Dependencies. 100% Type-Safe.</i></h5>

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
from monk.constraints import Email, Interval

@monk
class User:
    # No base class, no magic. Just your data.
    email: Annotated[str, Email]
    age: Annotated[int, Interval(ge=18)]

user = User(email="not-an-email", age=12)
validate(user)  # Captures BOTH email and age errors; doesn't fail-fast.
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

## The Toolkit
**Batteries included**. `iron-monk` comes with a comprehensive suite of built-in constraints, handling complex strings that other libraries ignore:
- 📝 **`CSV`**: Deeply validate comma-separated strings in-place without allocating lists in memory.
- ☁️ **`Cron`**: Structurally validate standard POSIX and strict AWS EventBridge scheduling strings.
- 🔒 **`JWT`**: Verify JSON Web Tokens structurally before passing them to heavy cryptography libraries.
- 📜 **`JSON`**: Ensure a string contains valid, parsable JSON without mutating it into a dictionary.
- 🔀 **`Not`**: Seamlessly invert the logic of any constraint (e.g., `Not(URL)`).

👉 [**Check out the Constraint Toolkit &rarr;**](https://benesgarage.github.io/iron-monk/constraints/)

 ## Performance
 `iron-monk` doesn't compromise on speed.
 
 *Tested on Python 3.13, executing 100,000 simple primitive validations.*

| Metric                    | `iron-monk`<br>*(v0.18.2)* | `msgspec`<br>*(v0.18.6)* | `pydantic`<br>*(v2.10.6)* | `attrs`<br>*(v24.3.0)* | `marshmallow`<br>*(v3.26.1)* |
|---------------------------|----------------------------|--------------------------|---------------------------|------------------------|------------------------------|
| **Package Size**          | **`0.06 MB`**              | `0.44 MB`                | `5.91 MB`                 | `0.21 MB`              | `0.17 MB`                    |
| **Cold Start**            | **`44.77ms`**              | `52.62ms`                | `83.46ms`                 | `55.73ms`              | `56.01ms`                    |
| **Object (100k)**         | `0.185s`                   | `0.014s`                 | `0.060s`                  | `0.089s`               | N/A                          |
| **Dict (100k)**           | `0.067s`                   | `0.059s`                 | `0.057s`                  | N/A                    | `0.445s`                     |
| **Nested Dict (100k)**    | `0.280s`                   | `0.075s`                 | `0.062s`                  | N/A                    | `1.513s`                     |
| **Invalid Dict (100k)**   | `0.244s`                   | `0.091s`                 | `0.088s`                  | N/A                    | `1.117s`                     |
| **Sanitized Dict (100k)** | `0.083s`                   | `0.070s`                 | `0.058s`                  | N/A                    | `0.450s`                     |
| **Partial Dict (100k)**   | **`0.056s`**               | N/A                      | N/A                       | N/A                    | `0.293s`                     |
| **Function Call (100k)**  | `0.162s`                   | N/A                      | `0.065s`                  | N/A                    | N/A                          |

**The Takeaway:** While Rust-backed libraries win on raw loop speed, `iron-monk` is the most efficient choice for the modern cloud. With a footprint 100x smaller than `Pydantic` and significantly faster cold starts, it is the best-in-class validator for AWS Lambda, serverless environments, and CI/CD pipelines where install time and memory overhead are the real bottlenecks.

👉 [**See our benchmarking methodology &rarr;**](https://benesgarage.github.io/iron-monk/benchmarks/)

## Why iron-monk?
Most validation libraries do too much. They don't just check your data; they change it. iron-monk is different:

- ❌ **No Coercion**: We won't "helpfully" turn your string "123" into an integer. If it's the wrong format, it's an error. Period.
- ❌ **No Base Classes**: Stop inheriting from BaseModel. Keep your classes clean and your IDE's autocompletion fast.
- ❌ **No Compilation**: Pure Python. No gcc or Rust toolchains required. It just works, everywhere.
- ❌ **No Side Effects**: Validating an object should never mutate its state. We keep your data exactly as you provided it.

## Real-world examples
`iron-monk` is designed to drop into any modern Python project. Some notable projects include:
- 🍓 Strawberry GraphQL: `iron-monk` helps validate `input` objects seamlessly. 
- ⚡ Starlette (ASGI): HTTP endpoints with simple request validation using `iron-monk`. 
- 🖥️ tyro (CLI tool): Generate command-line interfaces from dataclasses and validate with `iron-monk`.

👉 [**See `iron-monk` integrate with these projects, and more &rarr;**](https://benesgarage.github.io/iron-monk/examples/)

## 📚 Documentation
Ready to go deeper? Explore our guides:

* **[Core Concepts](https://benesgarage.github.io/iron-monk/core_concepts/)**: Understand the validation lifecycle and error extraction.
* **[Advanced Usage](https://benesgarage.github.io/iron-monk/advanced/)**: Multi-field validation and custom error messages.
* **[Custom Constraints](https://benesgarage.github.io/iron-monk/advanced/customization/)**: Learn how to build your own reusable constraints in 3 lines of code.

## License
MIT