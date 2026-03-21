# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0]

### Added
- **Return Type Validation:** The `@monk` decorator now automatically validates function return values! If a function's return type hint includes `Annotated` constraints (e.g., `-> Annotated[str, LowerCase]`), `iron-monk` will safely intercept and validate the output before returning it to the caller. This works for both synchronous and asynchronous functions.

## [0.7.0]

### Added
- **Function and Method Validation:** The `@monk` decorator is now dual-purpose! It can be applied directly to standard Python functions (sync and async), as well as class methods (`@classmethod`, `@staticmethod`, and instance methods). It intercepts calls, validates incoming arguments against your `Annotated` constraints, and aggregates failures into a standard `ValidationError` before the routine executes.

## [0.6.1]

### Fixed
- **Framework Interoperability:** Relaxed the `__getattribute__` guard to natively allow access to internal single-underscore variables (e.g., `_sa_instance_state`), fixing compatibility with SQLAlchemy's `MappedAsDataclass` and other instrumentation tools.
- **Generic Unwrapping:** The constraint extraction engine now intelligently peeks inside framework-specific generic wrappers (like SQLAlchemy's `Mapped[...]`) to find nested `Annotated` constraints.
- **Type Checker Signatures:** Shifted the deferred validation trigger from overriding `__init__` to injecting a `__post_init__` hook. This flawlessly preserves the dataclass's original `__init__` signature, allowing zero-friction integration with runtime type checkers like `beartype`.

### Added
- **Documentation:** Added real-world examples for `beartype` and `SQLAlchemy 2.0` integrations.

## [0.6.0]

### Added
- **Explicit Nullability:** Fields with constraints are now strictly required by default. Passing `None` to a constrained field instantly raises a validation error with the `NotNull` code.
- **`Nullable` and `NotNull` Markers:** Added explicit marker constraints to dictate presence. These markers can be used at the top-level or deeply nested inside collections (e.g., `Each(Nullable, LowerCase)`).
- **Type-Checker Compatibility:** Added `settings.default_allow_none` (and the `MONK_DEFAULT_ALLOW_NONE` environment variable) to allow `None` values globally by default. This allows developers to pair `iron-monk` with dedicated runtime type-checkers (like `beartype` or `typeguard`).
- **Core Concepts Guide:** Restructured the documentation into a clean, logical progression, separating Core Concepts from Advanced Usage.

### Changed
- **Constraint Boilerplate Eradicated:** Removed implicit `None` skipping from all built-in constraints. The engine now handles nullability structurally before constraint execution. Custom constraints no longer need to implement `if value is None: return`!
- **Philosophy Terminology:** Updated documentation phrasing to emphasize "Zero Coercion" and "Agnostic to Type Checking" to clearly define framework boundaries.

## [0.5.0]

### Added
- **Custom Error Codes:** All built-in constraints now accept an optional `code` argument to override the default class name for enterprise API responses.

### Changed
- **Error Dictionary Keys:** Renamed the `constraint` key to `code` in the structured error dictionaries (`ErrorDict`) and JSON outputs to better align with enterprise API standards.

## [0.4.0]

### Added
- **Error Formatting Helper:** Added `ValidationError.flatten()`, which returns a flat list of `{field}: {message}` strings. Perfect for CLI printouts or basic application logging.
- **Exception Messaging:** Unhandled `ValidationError` exceptions now automatically include the flattened error strings directly in their standard Python traceback message.
- **Strict Error Typing:** Introduced the `ErrorDict` type hint for `e.errors`. This preserves native JSON serialization for web frameworks while giving developers IDE autocomplete for `field`, `message`, and `constraint` keys.

### Changed
- **Punchier Configuration:** Renamed the `deferred_validation` argument to simply `defer`. This applies to the `@monk(defer=False)` decorator, `settings.defer`, and the `MONK_DEFER` environment variable.
- **Field-Agnostic Constraints:** Removed the `field: str` parameter from the `validate()` method signature across all constraints. Custom constraints must now implement `validate(self, value: Any) -> None`. This removes framework boilerplate when writing custom rules. Path tracking is now handled implicitly by the core engine.

## [0.3.1]

### Fixed
- Added the official MkDocs documentation link to PyPI metadata.

## [0.3.0]

### Added
- **Model-Level (Cross-Field) Validation:** Added support for the `__monk_validate__` hook, allowing developers to validate multiple fields together.
- **Flexible Error Yielding:** The new hook accepts generators, lists, or single returns consisting of strings (for root errors), 2-tuples, or 3-tuples.
- **Type Aliases:** Exported the `MonkError` type alias to provide IDE autocomplete and type-checking when writing cross-field validation methods.

## [0.2.0]

### Added
- **Custom Error Messages:** All built-in constraints now support an optional `message` argument for completely custom error outputs.
- **Safe String Interpolation:** Custom messages support safe `{value}` interpolation, as well as accessing constraint properties (e.g., `{ge}`, `{min_len}`).
- **Nested Interpolation:** The `Not` constraint can now safely interpolate properties from its inner constraint (e.g., `{constraint.ge}`).
- Added a comprehensive `docs/` directory with detailed tutorials, integration examples, and architectural explanations.

### Changed
- Refactored all remaining "Singleton" constraints (`Email`, `URL`, `UUID`, etc.) into standard `@constraint` dataclasses to support custom messages and uniform instantiation.
- The `@constraint` decorator now automatically wraps validation methods to handle custom message interpolation.

## [0.1.3]

### Added
- Added `IsDir` and `IsFile` file system constraints.

### Fixed
- **Caching Compatibility:** The `OneOf` constraint now strictly casts choices to a `tuple` making it fully hashable and natively compatible with `tyro` and `FastAPI` dependency caching.

## [0.1.2]

### Added
- Added comprehensive `examples/` directory showcasing real-world integrations with **Strawberry GraphQL** and **Application Configuration**.

### Changed
- **API-Ready Error Messages:** Constraint error strings are now field-agnostic (e.g., `"Must be a valid email address."`), ready for frontend consumption without leaking backend database variables.

### Fixed
- **Holistic Iterables:** The `Each` constraint no longer fails-fast. It now aggregates all nested failures and perfectly resolves deep dot-notation paths (e.g., `"matrix[0][1]"` instead of `"At index 0:"`).
- **Framework Compatibility:** Erased the internal `__monk_safe__` state flag from dataclass metadata immediately after compilation. This prevents the flag from leaking into OpenAPI/GraphQL schemas and fixes initialization crashes when used with aggressive parsing frameworks like Strawberry or FastAPI.
- Fixed strict MyPy type-checking errors related to dynamic dataclass attribute assignment.

### Removed
- Removed `twine` from `dev` dependencies as PyPI publishing is entirely handled by GitHub Actions CI/CD.

## [0.1.1]

### Added
- Expanded support to include **Python 3.11 and 3.12**.
- Added forward compatibility for Python 3.14 (PEP 649 deferred annotations).

### Fixed
- **Typing:** Upgraded decorators with strict `@overload` signatures, improving MyPy compatibility and IDE autocomplete for end-users.
- Replaced dynamic `__dict__` assignments with `setattr` to ensure compliance with strict static analysis tools.

## [0.1.0] - Initial Release

### Added
- Initial release of `iron-monk` with deferred validation, strict typing, and the core constraint toolkit.