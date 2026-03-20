from typing import TypeAlias, TypedDict


class ErrorDict(TypedDict):
    field: str
    message: str
    constraint: str


# A single validation error can be a string (for root errors) or a tuple.
MonkError: TypeAlias = str | tuple[str] | tuple[str, str] | tuple[str, str, str]
