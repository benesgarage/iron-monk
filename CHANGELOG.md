# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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