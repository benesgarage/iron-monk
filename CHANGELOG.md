# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.22.0]

### Removed
- **Ignored Sentinels:** Removed the `settings.ignored_sentinels` feature. Framework bypasses (like `UNSET`) should now be natively expressed and routed using standard Python `Union` type boundaries (e.g. `int | UnsetType`).

## [0.21.0]

### Added
- **Framework Type Metadata:** Added `settings.type_metadata` to configure the compile-time schema globally. You can now seamlessly map custom generic classes (like `strawberry.Maybe`) to a set of predefined constraints (like `[Nullable]`).
- **Two-Phase Nullability:** We now distinguish between omitted fields (outer nullability) and explicitly wrapped nulls (inner nullability, e.g., `Some(None)`).
- **Generic Wrapper Peeling:** Fixed unions within generic wrappers, allowing deeply nested unions to route successfully.

## [0.20.0]

### Added
- **Native Union Routing:** `iron-monk` now natively intercepts `Union` and the `|` operator. Validation is routed to the correct branch, and if no branch is satisfied, an aggregated "Must satisfy at least one" error is thrown.
- **Native Optional Fields:** Standard Python optionality (e.g., `Annotated[str, Email] | None`) is now natively supported. The explicit `Nullable` constraint is no longer required for class or function type hints (though it remains available for functional APIs like `validate_stream` and `Each`).

### Removed (Breaking)
- **Optional Type Aliases:** Removed `OptStr`, `OptInt`, `OptFloat`, `OptBool`, and `OptAny` type aliases from `monk.constraints`. With native union routing, standard Python syntax (`| None`) is the recommended approach.

### Maintenance
- **Dependencies:** Bumped internal development, testing, and integration dependencies to their latest versions via `uv`.

## [0.19.2]

### Fixed
- **Initialization Hooks:** Temporarily allows access to object attributes during `__post_init__` to allow third-party validation hooks (like Strawberry's `one_of=True` checks) to safely read instance attributes before deferred validation locks them down.

## [0.19.1]

### Added
- **Optional Type Aliases:** Added built-in type aliases (`OptStr`, `OptInt`, `OptFloat`, `OptBool`, `OptAny`) to the `monk.constraints` module to reduce `str | None` and `Nullable` boilerplate when defining schemas with many optional fields.

## [0.19.0]

### Added
- **Framework Unwrappers:** Added `settings.unwrappers` to teach `iron-monk` how to extract values from wrapper objects (like Strawberry's `Maybe`/`Some`).
- **Ignored Sentinels:** Added `settings.ignored_sentinels` to skip validation for omitted-field markers (like `UNSET`).

## [0.18.3]

### Added
- **Dynamic Dictionaries:** Added the `DictOf` constraint to validate arbitrary dictionaries with dynamic keys.
- **Cloud Scheduling:** Added the `Cron` constraint to structurally validate standard 5-field POSIX cron expressions and 6-field AWS EventBridge formats.
- **Modern Auth:** Added the `JWT` constraint to structurally validate JSON Web Tokens without pulling in heavy cryptography dependencies.
- **ISO 8601 Dates:** Added the `IsISO8601` constraint to validate that a string is a properly formatted ISO 8601 date or datetime.

## [0.18.2]

### Changed
- **Performance:** Implemented optimizations by inlining validation logic and removing function call overhead, resulting in a ~30% performance increase for nested dictionary validation.
- **Benchmark Fairness:** Updated the benchmark script to ensure all frameworks use `TypedDict` schemas for nested dictionary validation, creating a fair, apples-to-apples comparison of dictionary allocation overhead.

 ## [0.18.1]
 
 ### Fixed
 - **PEP 561 Compliance:** Added the `py.typed` marker file so external type checkers (like MyPy and Pyright) natively recognize type hints when installed in downstream projects.

 ## [0.18.0]
 
 ### Changed (Breaking)
 - **CSV Coercion Removed:** Removed the `strip` parameter from the `CSV` constraint to strictly enforce the library's "Zero Coercion" philosophy. The constraint now accurately evaluates the exact literal substrings produced by `.split()`.
 - **CSV Error Aggregation:** The `CSV` constraint now holistically aggregates multiple errors and raises a `ValidationError` (matching the behavior of `Each`), instead of failing fast with a `ValueError`.
 - **CSV Uniqueness:** Added the `unique=True` flag to the `CSV` constraint to safely validate element uniqueness across the string without character-level traversal bugs.

## [0.17.1]

### Added
- **CSV Constraint:** Added the `CSV` constraint to validate delimited strings (like URL query parameters) element-by-element.

## [0.17.0]

### Added
- **Toolkit Expansion:** Added 15 new built-in constraints to cover standard use cases:
  - **Strings & Formats:** `IsAlpha`, `IsAlnum`, `Trimmed`, `ExactLen`, `Slug`, `SemVer`, `Base64`, `HexColor`, `JSON`
  - **Networking & Geospatial:** `MacAddress`, `Port`, `LatLong`
  - **Collections:** `ContainsKeys`, `Subset`
  - **Datetime:** `Past`, `Future`

## [0.16.3]

### Added
- **Integration testing:** Built a fully isolated integration testing suite (`tests_integration/`) that continuously proves `iron-monk`'s compatibility with Starlette, Strawberry GraphQL, SQLAlchemy, Tortoise ORM, `tyro`, and `beartype`.
- **Ecosystem Monitoring:** Added a dedicated GitHub Actions workflow to test integration compatibility against upstream framework updates.

### Changed
- **Documentation Overhaul:** Completely rewrote the documentation to be sleek, punchy, and no-nonsense.
- **CI/CD Pipeline:** Migrated all GitHub Actions workflows to use `uv` (`astral-sh/setup-uv`), drastically reducing CI build and execution times.

## [0.16.2]

### Fixed
- **Pyright & VS Code:** Achieved 100% strict-mode compliance with Pyright/Pylance.
- **Ecosystem:** Expanded PyPI classifiers and keywords to improve searchability.

## [0.16.1]

### Changed
- **Performance Optimizations:** Significantly increased execution speed across the board. Object instantiation overhead was nearly halved by pre-caching dataclass fields. Dictionary validation throughput was boosted by fast-pathing primitive types and eliminating redundant `set` memory allocations during sanitization checks. Nested dictionary validation overhead was reduced by caching module imports.

## [0.16.0]

### Added
- **RFC 7807 Enterprise Errors:** Added a `.to_rfc7807()` method to the `ValidationError` exception. This allows developers to format validation failures into standard RFC 7807 Problem Details JSON dictionaries.

## [0.15.0]

### Added
- **Recursive Schemas:** The `Nested` constraint now accepts a `lambda` (e.g., `Nested(lambda: MySchema)`), enabling the validation of recursive and self-referencing JSON dictionary structures (like file trees or comment threads) without breaking Python's sequential execution or relying on heavy string-evaluation magic.

## [0.14.0]

### Added
- **Dictionary Sanitization:** Added the `drop_extra_keys=True` flag to `validate_dict()`. This allows developers to sanitize input dictionaries by stripping out any keys not explicitly defined in the schema.

## [0.13.0]

### Added
- **Deeply Nested Dictionary Validation:** Added the `Nested` constraint, bridging the gap for validating deep JSON architectures (like lists of nested dictionaries) using `validate_dict`. This allows developers to validate infinitely complex `TypedDict` trees without instantiating a single object.

## [0.12.0]

### Added
- **Partial Validation (PATCH Support):** Added the `partial=True` flag to `validate_dict()`. This allows developers to validate partial dictionary payloads against their existing `@monk` dataclasses by ignoring fields that are omitted.

### Changed
- **Architectural Guardrails:** The core engine now explicitly checks for and rejects asynchronous `__monk_validate__` hooks, raising a `TypeError`.
- **Documentation:** Restructured the Advanced Usage documentation into a modular guide.

## [0.11.0]

### Added
- **Logical Composability:** Added `AnyOf` (Logical OR) and `AllOf` (Logical AND) constraints. These higher-order constraints allow you to build complex, nested business rules (like accepting multiple formats for a single field) and group multiple constraints under a single custom error message or code.

## [0.10.0]

### Added
- **Stream and Generator Validation:** Added `validate_stream` and `validate_async_stream` utilities to explicitly and lazily validate streams on the fly. This prevents memory bloat by yielding and validating items one by one, instantly raising a `ValidationError` if an item violates your constraints.

## [0.9.1]

### Fixed
- **Exhaustible Iterator Protection:** Constraints that iterate over collections (`Each`, `Contains`, `Unique`) now explicitly reject exhaustible iterators (like generators and streams) by raising a `TypeError`. This prevents difficult-to-debug "silent consumption" bugs where validation would exhaust a stream and leave the application with empty data.

### Added
- **Generator Documentation:** Added a dedicated section in the Advanced Usage guide explaining how to safely handle, materialize, and validate generators and data streams.

## [0.9.0]

### Added
- **Raw Dictionary Validation:** Added the `validate_dict(data, schema)` function to natively validate raw Python dictionaries against `TypedDict` schemas. This provides performance benefits for high-throughput applications (like WebSockets or data pipelines) by entirely skipping object instantiation and memory allocation while retaining the full constraint toolkit

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