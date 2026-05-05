# Advanced Usage

Tools for complex data flows and customized error handling:

- [**Dicts, Streams, & Execution**](advanced/execution.md): Validate raw dictionaries, handle `PATCH` updates, validate streams lazily, and execute standalone constraints.
- [**Cross-Field Validation**](advanced/cross_field.md): Implement rules that depend on multiple fields simultaneously.
- [**Asymmetric Validation**](advanced/asymmetric_validation.md): Implement rules for one field that depends on others.
- [**Logical Composability**](advanced/logical.md): Combine rules using `AnyOf`, `AllOf`, and `Not`.
- [**Custom Constraints & Errors**](advanced/customization.md): Override default error messages and JSON codes, or build custom constraints.