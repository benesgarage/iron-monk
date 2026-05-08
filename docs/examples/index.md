# Integrations

`iron-monk` is a single decorator with no metaclass tricks, so it slots into any framework that lets you decorate a class or call a function. The pages below are battle-tested recipes — copy, paste, adapt.

| If you are using… | Read |
| --- | --- |
| **Strawberry GraphQL** | [Strawberry GraphQL](strawberry.md) — `errors-as-data` for inputs, fail-fast for headers, `Maybe[T]` integration via `settings.type_metadata`. |
| **Starlette / ASGI** | [Starlette (ASGI)](starlette.md) — RFC 7807 exception handlers, dict-mode and DTO-mode handlers. |
| **SQLAlchemy 2.0** | [SQLAlchemy 2.0](sqlalchemy.md) — validate ORM models before commit; `Mapped[T]` unwrapping. |
| **Tortoise ORM** | [Tortoise ORM](tortoise_orm.md) — split DTO validation from Active Record persistence. |
| **tyro CLI** | [tyro](tyro.md) — validate dataclass-driven CLIs alongside argument parsing. |
| **App startup config** | [App Configuration](app_config.md) — fail-fast environment variable validation on boot. |
| **beartype runtime types** | [Beartype](beartype.md) — stack runtime type checking under business constraints. |

Don't see your stack? The pattern is always the same — annotate, decorate, validate at the boundary. Open an issue with your use case and it will likely become a new page.
