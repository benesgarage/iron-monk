# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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