import datetime
import ipaddress
import math
import re
import uuid
from collections.abc import Iterable, Sized
from dataclasses import field
from typing import Any, Callable, Annotated
from urllib.parse import urlparse

from .protocols import MonkConstraint, SupportsGt, SupportsGe, SupportsLt, SupportsLe, SupportsMod
from .decorators import constraint
from .exceptions import ValidationError


@constraint
class Predicate:
    """Validates that a value satisfies a given boolean-returning function."""

    func: Callable[..., bool]

    def validate(self, field: str, value: Any) -> None:
        if value is None:
            return
        try:
            if not self.func(value):
                func_name = getattr(self.func, "__name__", "custom predicate")
                raise ValueError(f"Failed validation for {func_name}.")
        except TypeError:
            # Catches cases where a user passes the wrong type to a strict function (e.g. an int to str.islower)
            func_name = getattr(self.func, "__name__", "custom predicate")
            raise TypeError(f"Type '{type(value).__name__}' is incompatible with predicate '{func_name}'.")


@constraint
class Not:
    """Inverts the logic of another constraint."""

    constraint: MonkConstraint

    def validate(self, field: str, value: Any) -> None:
        if value is None:
            return
        try:
            self.constraint.validate(field, value)
        except (ValueError, TypeError):
            return  # The inner constraint failed, meaning 'Not' is satisfied!

        constraint_name = getattr(type(self.constraint), "__name__", "specified constraint")
        raise ValueError(f"Must not satisfy {constraint_name}.")


@constraint(kw_only=True)
class Interval:
    """Numeric or Comparable Interval bounds"""

    gt: SupportsGt | None = None
    ge: SupportsGe | None = None
    lt: SupportsLt | None = None
    le: SupportsLe | None = None

    def validate(self, field: str, value: Any) -> None:
        if value is None:
            return

        try:
            if self.gt is not None and not (value > self.gt):
                raise ValueError(f"Must be strictly greater than {self.gt}.")
            if self.ge is not None and not (value >= self.ge):
                raise ValueError(f"Must be greater than or equal to {self.ge}.")
            if self.lt is not None and not (value < self.lt):
                raise ValueError(f"Must be strictly less than {self.lt}.")
            if self.le is not None and not (value <= self.le):
                raise ValueError(f"Must be less than or equal to {self.le}.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' does not support comparison for interval bounds.")


LowerCase = Predicate(str.islower)
UpperCase = Predicate(str.isupper)
IsDigit = Predicate(str.isdigit)
IsAscii = Predicate(str.isascii)

IsFinite = Predicate(math.isfinite)
IsNan = Predicate(math.isnan)
IsInfinite = Predicate(math.isinf)
NonNegative = Interval(ge=0)

IsUTC = Predicate(lambda dt: dt.tzinfo is not None and dt.utcoffset() == datetime.timedelta(0))


@constraint
class Len:
    min_len: Annotated[int, NonNegative] = 0
    max_len: Annotated[int | None, NonNegative] = None

    def __post_init__(self) -> None:
        NonNegative.validate("min_len", self.min_len)
        if self.max_len is not None:
            NonNegative.validate("max_len", self.max_len)
            if self.min_len > self.max_len:
                raise ValueError(f"min_len ({self.min_len}) cannot be greater than max_len ({self.max_len}).")

    def validate(self, field: str, value: Any) -> None:
        if value is None:
            return

        try:
            length = len(value)
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' does not support len().")

        if length < self.min_len:
            raise ValueError(f"Must have a minimum length of {self.min_len}.")
        if self.max_len is not None and length > self.max_len:
            raise ValueError(f"Must have a maximum length of {self.max_len}.")


@constraint
class MultipleOf:
    multiple_of: SupportsMod

    def __post_init__(self) -> None:
        if self.multiple_of == 0:
            raise ValueError("multiple_of cannot be 0.")

    def validate(self, field: str, value: Any) -> None:
        if value is None:
            return

        try:
            if value % self.multiple_of != 0:
                raise ValueError(f"Must be a multiple of {self.multiple_of}.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' does not support modulo operation.")


@constraint
class Match:
    """Validates that a string matches a specific Regular Expression."""

    pattern: str
    _compiled: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Compile the regex upfront for maximum performance
        object.__setattr__(self, "_compiled", re.compile(self.pattern))

    def validate(self, field: str, value: Any) -> None:
        if value is None:
            return

        try:
            if not self._compiled.match(value):
                raise ValueError(f"Does not match the required pattern: {self.pattern}")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' does not support regex matching.")


@constraint
class OneOf:
    """Validates that a value is an exact member of a predefined set of choices."""

    choices: Iterable[Any]

    def __post_init__(self) -> None:
        # Convert to tuple for safety if it's an exhaustible iterator
        if not isinstance(self.choices, (list, set, tuple, frozenset)):
            object.__setattr__(self, "choices", tuple(self.choices))

        if not self.choices:
            raise ValueError("OneOf requires at least one choice.")

    def validate(self, field: str, value: Any) -> None:
        if value is None:
            return

        if value not in self.choices:
            allowed = ", ".join(repr(c) for c in self.choices)
            raise ValueError(f"Must be one of: [{allowed}], got {repr(value)}.")


@constraint
class Each:
    """Validates that every element in an iterable satisfies all the given constraints."""

    constraints: tuple[MonkConstraint, ...]

    def __init__(self, *constraints: MonkConstraint):
        if not constraints:
            raise ValueError("Each requires at least one constraint.")
        # Safely assign to a frozen dataclass
        object.__setattr__(self, "constraints", constraints)

    def validate(self, field: str, value: Any) -> None:
        if value is None:
            return

        if not isinstance(value, Iterable):
            raise TypeError(f"Type '{type(value).__name__}' is not iterable.")

        errors: list[dict[str, Any]] = []
        for i, item in enumerate(value):
            for c in self.constraints:
                try:
                    c.validate(f"{field}[{i}]", item)
                except ValidationError as e:
                    errors.extend(e.errors)
                except (ValueError, TypeError) as e:
                    errors.append({"field": f"{field}[{i}]", "message": str(e), "constraint": type(c).__name__})

        if errors:
            raise ValidationError(errors)


@constraint
class Contains:
    """Validates that a collection or string contains a specific item/substring."""

    item: Any

    def validate(self, field: str, value: Any) -> None:
        if value is None:
            return

        try:
            if self.item not in value:
                raise ValueError(f"Must contain {repr(self.item)}.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' does not support 'in' operator.")


class Unique:
    """Validates that all elements in a collection are unique."""

    @classmethod
    def validate(cls, field: str, value: Any) -> None:
        if value is None:
            return

        if not isinstance(value, Iterable):
            raise TypeError(f"Type '{type(value).__name__}' is not iterable.")

        # Convert to a sized collection to safely check length and handle exhaustible iterators
        if not isinstance(value, Sized):
            value = tuple(value)

        try:
            if len(set(value)) < len(value):
                raise ValueError("All elements must be unique.")
        except TypeError:
            # Fallback for unhashable items (e.g. list of lists, list of dicts) O(n^2)
            seen = []
            for item in value:
                if item in seen:
                    raise ValueError("All elements must be unique.")
                seen.append(item)


class Email:
    """Validates an email address using a standard structural regex."""

    # A robust, reliable structural regex that catches the vast majority of email typos
    _regex = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+\Z")

    @classmethod
    def validate(cls, field: str, value: Any) -> None:
        if value is None:
            return
        try:
            if not cls._regex.match(value):
                raise ValueError("Must be a valid email address.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as an email.")


@constraint
class StartsWith:
    prefix: str

    def validate(self, field: str, value: Any) -> None:
        if value is None:
            return

        try:
            if not value.startswith(self.prefix):
                raise ValueError(f"Must start with '{repr(self.prefix)}'")
        except (TypeError, AttributeError):
            raise TypeError(f"Type '{type(value).__name__}' does not support startswith().")


@constraint
class EndsWith:
    suffix: str

    def validate(self, field: str, value: Any) -> None:
        if value is None:
            return
        try:
            if not value.endswith(self.suffix):
                raise ValueError(f"Must end with '{repr(self.suffix)}'")
        except (TypeError, AttributeError):
            raise TypeError(f"Type '{type(value).__name__}' does not support endswith().")


class UUID:
    """Validates that a value is a valid UUID string or object"""

    @classmethod
    def validate(cls, field: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, uuid.UUID):
            return
        try:
            uuid.UUID(str(value))
        except ValueError:
            raise ValueError("Must be a valid UUID.")


class URL:
    """Validates that a string is a properly formatted URL"""

    @classmethod
    def validate(cls, field: str, value: Any) -> None:
        if value is None:
            return
        try:
            result = urlparse(str(value))
            if not all([result.scheme, result.netloc]):
                raise ValueError("Must be a valid URL.")
        except Exception:
            raise ValueError("Must be a valid URL.")


class IPAddress:
    """Validates that a value is a valid IPv4 or IPv6 address"""

    @classmethod
    def validate(cls, field: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            return
        try:
            ipaddress.ip_address(str(value))
        except ValueError:
            raise ValueError("Must be a valid IPv4 or IPv6 address.")
