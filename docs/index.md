<div align="center">
  <img src="assets/monk.png" width="400" alt="iron-monk logo">
  <h1>iron-monk</h1>
</div>

Welcome to the official documentation for **iron-monk**, a minimalist, zero-coercion validation library for Python dataclasses.

## The Philosophy
The Python ecosystem is dominated by heavy validation frameworks. 

If you are ingesting a 10,000-line JSON array from a data pipeline and need to coerce it, validate it, and serialize it back out thousands of times a second, Pydantic V2 or `msgspec` is the tool for the job.

But do 99% of developers need that? Absolutely not.

The vast majority of Python developers are building standard CRUD web APIs, CLI tools, or background workers. Their payloads look like this:
```json
{
  "username": "bob",
  "email": "test@domain.com",
  "age": 25
}
```

To validate those three fields, developers are currently installing libraries that download compiled Rust binaries, inject massive metaclasses into their objects, drastically slow down their server boot times (due to import overhead), and add megabytes of bloat to their Docker containers. It is the definition of using a sledgehammer to crack a nut.

`iron-monk` was built to provide a clean, explicitly-typed alternative:

- 🎯 **Do one thing well**: Unlike libraries that parse, coerce, and serialize, we focus strictly on validation.
- 🪶 **Zero Dependencies:** Pure Python. No compiled binaries or bloated environments.
- 🛡️ **Zero Coercion**: We don't secretly cast the string "123" into the integer 123. Your data is validated exactly as it is received.
- 🤝 **Agnostic to Type Checking:** We enforce *business constraints*, not base Python types.
- ⏳ **Deferred Validation:** Capture bad data in a guarded state instead of crashing instantly.
- 🧬 **Zero Inheritance:** No massive base classes polluting your namespace. Just a decorator.

### Validation vs. Type Checking
We draw a strict line between *Type Checking* ("Does this value match the Python type hint?") and *Value Validation* ("Does this value satisfy my business rules?"). 

`iron-monk` focuses entirely on the latter. It does not perform deep runtime type-checking. This means it works perfectly as a standalone framework for standard API validation, or it can stack flawlessly alongside dedicated strict typing tools like `beartype` or `typeguard` without stepping on their toes.

The one area where these lines blur is missing data (nullability). To learn how `iron-monk` enforces presence, or how to configure it to completely defer to an external type checker, read about [Required vs. Optional Fields](core_concepts.md#required-vs-optional-fields) and [Relying on Runtime Type Checkers](core_concepts.md#relying-on-runtime-type-checkers).

## Getting Started

To learn how to use the framework, check out:

1. [**Core Concepts**](core_concepts.md): Understand the validation lifecycle, how to extract errors, and required vs. optional fields.
2. [**The Constraint Toolkit**](constraints.md): A complete list of all built-in rules (like `Email`, `Interval`, and `Each`).
2. [**Advanced Usage**](advanced.md): Learn about Cross-Field validation, Fail-Fast mode, and Custom Error Messages.
3. [**Real-World Examples**](examples.md): See how to seamlessly drop `iron-monk` into frameworks like Strawberry GraphQL, Starlette, and Tyro.

```bash
pip install iron-monk
```