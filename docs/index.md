<div align="center">
  <img src="assets/monk.png" width="400" alt="iron-monk logo">
  <h1>iron-monk</h1>
</div>

Welcome to the official documentation for **iron-monk**, a minimalist, zero-coercion validation library for Python.

## The Philosophy
The Python ecosystem is dominated by heavy validation frameworks that do too much.

To validate a standard API payload, you shouldn't have to install a library that downloads compiled Rust binaries, injects massive metaclasses, slows down server boot times, and adds megabytes of bloat to your Docker containers.

`iron-monk` was built to provide a clean, explicitly-typed alternative:

- 🎯 **Do one thing well**: Unlike libraries that parse, coerce, and serialize, we focus on validation.
- 🪶 **Zero Dependencies:** Pure Python. No compiled binaries or bloated environments.
- 🛡️ **Zero Coercion**: We don't secretly cast the string "123" into the integer 123.
- 🤝 **Agnostic to Type Checking:** We enforce *business constraints*, not base Python types.
- ⏳ **Deferred Validation:** Capture bad data in a guarded state instead of crashing instantly.
- 🧬 **Zero Inheritance:** No massive base classes polluting your namespace. Just a decorator.

### Validation vs. Type Checking
We draw a strict line between *Type Checking* ("Does this value match the Python type hint?") and *Value Validation* ("Does this value satisfy my business rules?"). 

`iron-monk` focuses entirely on the latter. By skipping deep runtime type-checking, it operates perfectly as a standalone validator or stacks flawlessly alongside dedicated tools like `beartype` or `typeguard`.

To configure how `iron-monk` handles missing data (nullability), see [Required vs. Optional Fields](core_concepts.md#required-vs-optional-fields) and [Relying on Runtime Type Checkers](core_concepts.md#relying-on-runtime-type-checkers).

## Getting Started

```bash
pip install iron-monk
```

Dive into the documentation:

1. [**Core Concepts**](core_concepts.md): The validation lifecycle, error extraction, and nullability.
2. [**The Constraint Toolkit**](constraints.md): A complete reference of all built-in rules (e.g. `Email`, `Interval`, `Nested`).
2. [**Advanced Usage**](advanced.md): Raw dictionaries, partial updates (PATCH), lazy streams, and cross-field logic.
3. [**Real-World Examples**](examples.md): Drop-in integrations for Strawberry GraphQL, Starlette, ORMs, and CLI tools.
