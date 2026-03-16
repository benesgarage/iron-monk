from typing import Any, Protocol, runtime_checkable


class SupportsGt(Protocol):
    def __gt__(self, other: Any) -> bool: ...


class SupportsGe(Protocol):
    def __ge__(self, other: Any) -> bool: ...


class SupportsLt(Protocol):
    def __lt__(self, other: Any) -> bool: ...


class SupportsLe(Protocol):
    def __le__(self, other: Any) -> bool: ...


class SupportsMod(Protocol):
    def __mod__(self, other: Any) -> Any: ...


@runtime_checkable
class MonkConstraint(Protocol):
    def validate(self, field: str, value: Any) -> None:
        ...