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
