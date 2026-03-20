# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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