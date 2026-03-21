# Real-World Examples

Designed to drop into any modern Python project, here are some examples where `iron-monk` shines:

### 🌐 Web & API
- 🍓 [**Strawberry GraphQL**](examples/strawberry.md): Showcases the "Errors as Data" pattern with deferred inputs, plus fail-fast context/header protection.
- ⚡ [**Starlette (ASGI)**](examples/starlette.md): Build HTTP endpoints with simple request validation using `iron-monk`.

### ⚙️ Configuration & CLI
- 🖥️ [**tyro (CLI tool)**](examples/tyro.md): Generate command-line interfaces from dataclasses and validate with `iron-monk`.
- ⚙️ [**App Configuration**](examples/app_config.md): Explicit, fail-fast environment variable validation for robust application boot sequences.

### 🛡️ Typing & Ecosystem
- 🐻 [**Beartype**](examples/beartype.md): Stack runtime type-checking alongside your business constraints.

### 🗄️ Data & ORMs
- 🗄️ [**SQLAlchemy 2.0**](examples/sqlalchemy.md): Validate your ORM models safely before committing transactions to your database.