# Advanced Usage

As your application scales, you may need more than just standard dataclass validation. `iron-monk` provides powerful tools for complex data flows, edge-case routing, and highly customized error handling.

Choose a topic to dive deeper:

- [🚀 **Dicts, Streams, & Execution**](advanced/execution.md): Learn how to validate raw dictionaries, handle partial `PATCH` updates, validate infinite streams lazily, and execute constraints directly on standalone variables.
- [🔗 **Cross-Field Validation**](advanced/cross_field.md): Implement model-level validation rules that depend on multiple fields simultaneously.
- [🧠 **Logical Composability**](advanced/logical.md): Combine rules using `AnyOf`, `AllOf`, and `Not` to build complex, nested business logic.
- [🛠️ **Custom Constraints & Errors**](advanced/customization.md): Override default error messages and JSON codes, or build your own high-performance constraints from scratch.