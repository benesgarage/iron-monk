# Real-World Examples

`iron-monk` drops seamlessly into any modern Python project.

### 🌐 Web & API
- [**Strawberry GraphQL**](examples/strawberry.md): Use "Errors as Data" for inputs and fail-fast protection for headers.
- [**Starlette (ASGI)**](examples/starlette.md): Validate incoming HTTP request payloads.

### ⚙️ Configuration & CLI
- [**tyro (CLI tool)**](examples/tyro.md): Validate dataclass-driven command-line interfaces.
- [**App Configuration**](examples/app_config.md): Fail-fast environment variable validation for safe application boots.

### 🛡️ Typing & Ecosystem
- [**Beartype**](examples/beartype.md): Stack runtime type-checking alongside business constraints.

### 🗄️ Data & ORMs
- [**SQLAlchemy 2.0**](examples/sqlalchemy.md): Validate ORM models before committing database transactions.
- [**Tortoise ORM**](examples/tortoise_orm.md): Use DTOs to cleanly separate API validation from Active Record persistence.