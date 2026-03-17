from typing import Any


class UnvalidatedAccessError(Exception):
    """
    Raised when attempting to access an attribute on a Monk object
    before validate() has been successfully called.
    """

    pass


class ValidationError(Exception):
    """
    Raised when validation fails for one or more fields on a Monk object.
    Contains a list of all validation errors.
    """

    def __init__(self, errors: list[dict[str, Any]]):
        self.errors = errors
        error_count = len(errors)
        plural = "" if error_count == 1 else "s"

        lines = [f"{error_count} validation error{plural} found:"]
        for error in errors:
            lines.append(f"  - {error['field']}: {error['message']}")

        super().__init__("\n".join(lines))
