# Advanced Usage

Four pages cover everything beyond the basics. Each is scoped to one mental model — pick the one that matches your problem.

| Page | Use it when |
| --- | --- |
| **[Cross-Field Validation](cross_field.md)** | One field's rule depends on another. Covers `Ref` (declarative) and the `__monk_validate__` hook (programmatic). |
| **[Customization](customization.md)** | You want custom error messages, custom error codes, or you are building your own constraint. |
| **[Execution Models](execution.md)** | You hit the edges of `validate_dict` (partial, sanitization), need streaming validation, or want recursive / nested schemas. |
| **[Settings and Type Metadata](settings.md)** | You are integrating with a framework that wraps values, uses sentinels, or expresses optionality through a custom generic. |

If your question is *"what does built-in constraint X do?"*, that lives in the **[Constraints catalog](../constraints.md)** instead.
