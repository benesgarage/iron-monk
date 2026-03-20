from typing import TypeAlias

# A single validation error can be a string (for root errors) or a tuple.
MonkError: TypeAlias = str | tuple[str] | tuple[str, str] | tuple[str, str, str]
