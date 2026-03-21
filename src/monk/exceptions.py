from typing import Any
from .types import ErrorDict


class UnvalidatedAccessError(Exception):
    """
    Raised when attempting to access an attribute on a Monk object
    before validate() has been successfully called.
    """

    pass


class ValidationError(Exception):
    errors: list[ErrorDict]

    def __init__(self, errors: list[ErrorDict]):
        self.errors = errors
        error_msg = ", ".join(self.flatten())
        super().__init__(f"Validation failed: {error_msg}")

    def flatten(self) -> list[str]:
        """Returns a flat list of formatted error strings."""
        return [f"{err['field']}: {err['message']}" for err in self.errors]

    def to_rfc7807(
        self,
        status: int = 400,
        title: str = "Validation Error",
        type_uri: str = "about:blank",
        detail: str = "The provided data is invalid. See 'errors' for specific details.",
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Formats the errors into an RFC 7807 compliant dictionary for HTTP APIs."""
        payload: dict[str, Any] = {
            "type": type_uri,
            "title": title,
            "status": status,
            "detail": detail,
            "errors": self.errors,
        }
        if instance is not None:
            payload["instance"] = instance

        return payload
