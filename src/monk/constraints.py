import datetime
import ipaddress
import math
import re
import uuid
import pathlib
from collections.abc import Iterable, Sized
from dataclasses import field
from typing import Any, Callable, Annotated, cast
from urllib.parse import urlparse

from .protocols import MonkConstraint, SupportsGt, SupportsGe, SupportsLt, SupportsLe, SupportsMod
from .decorators import constraint
from .exceptions import ValidationError
from .types import ErrorDict
from .config import settings


@constraint
class Predicate:
    """Validates that a value satisfies a given boolean-returning function."""

    func: Callable[..., bool]
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
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

    constraint: MonkConstraint | type[Any]
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.constraint, type) and issubclass(self.constraint, MonkConstraint):
            try:
                object.__setattr__(self, "constraint", self.constraint())
            except TypeError as e:
                raise TypeError(
                    f"Constraint '{self.constraint.__name__}' missing required arguments. Did you mean {self.constraint.__name__}(...)?"
                ) from e

    def validate(self, value: Any) -> None:
        try:
            cast(MonkConstraint, self.constraint).validate(value)
        except (ValueError, TypeError):
            return  # The inner constraint failed, meaning 'Not' is satisfied!

        constraint_name = getattr(type(self.constraint), "__name__", "specified constraint")
        raise ValueError(f"Must not satisfy {constraint_name}.")


@constraint
class Nullable:
    """A marker constraint to explicitly allow None values."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        pass


@constraint
class NotNull:
    """A marker constraint to explicitly forbid None values."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        pass


@constraint(kw_only=True)
class Interval:
    """Numeric or Comparable Interval bounds"""

    gt: SupportsGt | None = None
    ge: SupportsGe | None = None
    lt: SupportsLt | None = None
    le: SupportsLe | None = None
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        try:
            if self.gt is not None and not (value > self.gt):
                raise ValueError(f"Must be greater than {self.gt}.")
            if self.ge is not None and not (value >= self.ge):
                raise ValueError(f"Must be greater than or equal to {self.ge}.")
            if self.lt is not None and not (value < self.lt):
                raise ValueError(f"Must be less than {self.lt}.")
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
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        NonNegative.validate(self.min_len)
        if self.max_len is not None:
            NonNegative.validate(self.max_len)
            if self.min_len > self.max_len:
                raise ValueError(f"min_len ({self.min_len}) cannot be greater than max_len ({self.max_len}).")

    def validate(self, value: Any) -> None:
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
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        if self.multiple_of == 0:
            raise ValueError("multiple_of cannot be 0.")

    def validate(self, value: Any) -> None:
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
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        # Compile the regex upfront for maximum performance
        object.__setattr__(self, "_compiled", re.compile(self.pattern))

    def validate(self, value: Any) -> None:
        try:
            if not self._compiled.match(value):
                raise ValueError(f"Does not match the required pattern: {self.pattern}")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' does not support regex matching.")


@constraint
class OneOf:
    """Validates that a value is an exact member of a predefined set of choices."""

    choices: Iterable[Any]
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        # Always convert to tuple so the constraint is immutable and hashable (for tyro/FastAPI caching)
        object.__setattr__(self, "choices", tuple(self.choices))

        if not self.choices:
            raise ValueError("OneOf requires at least one choice.")

    def validate(self, value: Any) -> None:
        if value not in self.choices:
            allowed = ", ".join(repr(c) for c in self.choices)
            raise ValueError(f"Must be one of: [{allowed}], got {repr(value)}.")


@constraint
class Each:
    """Validates that every element in an iterable satisfies all the given constraints."""

    constraints: tuple[MonkConstraint, ...]
    allow_none: bool = field(default=False, init=False, repr=False, compare=False)
    not_null_constraint: Any = field(default=None, init=False, repr=False, compare=False)

    def __init__(self, *constraints: MonkConstraint | type[Any]):
        if not constraints:
            raise ValueError("Each requires at least one constraint.")

        instantiated_constraints: list[MonkConstraint] = []
        allow_none = settings.default_allow_none
        not_null_constraint: Any = None

        for c in constraints:
            if c is Nullable or isinstance(c, Nullable):
                allow_none = True
                continue
            if c is NotNull or isinstance(c, NotNull):
                allow_none = False
                not_null_constraint = c() if isinstance(c, type) else c
                continue

            if isinstance(c, type) and issubclass(c, MonkConstraint):
                try:
                    instantiated_constraints.append(c())
                except TypeError as e:
                    raise TypeError(
                        f"Constraint '{c.__name__}' missing required arguments. Did you mean {c.__name__}(...)?"
                    ) from e
            else:
                instantiated_constraints.append(cast(MonkConstraint, c))

        if not instantiated_constraints:
            raise ValueError("Each requires at least one functional constraint besides markers like Nullable/NotNull.")

        # Safely assign to a frozen dataclass
        object.__setattr__(self, "constraints", tuple(instantiated_constraints))
        object.__setattr__(self, "allow_none", allow_none)
        object.__setattr__(self, "not_null_constraint", not_null_constraint)

    def validate(self, value: Any) -> None:
        if not isinstance(value, Iterable):
            raise TypeError(f"Type '{type(value).__name__}' is not iterable.")

        errors: list[ErrorDict] = []
        for i, item in enumerate(value):
            if item is None:
                if self.allow_none:
                    continue
                else:
                    msg = getattr(self.not_null_constraint, "message", None) or "Field is required and cannot be null."
                    code = getattr(self.not_null_constraint, "code", None) or "NotNull"
                    errors.append({"field": f"[{i}]", "message": msg, "code": code})
                    continue

            for c in self.constraints:
                try:
                    c.validate(item)
                except ValidationError as e:
                    for err in e.errors:
                        err["field"] = f"[{i}]{err.get('field', '')}"
                        errors.append(err)
                except (ValueError, TypeError) as e:
                    error_code = getattr(c, "code", None) or type(c).__name__
                    errors.append({"field": f"[{i}]", "message": str(e), "code": error_code})

        if errors:
            raise ValidationError(errors)


@constraint
class Contains:
    """Validates that a collection or string contains a specific item/substring."""

    item: Any
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        try:
            if self.item not in value:
                raise ValueError(f"Must contain {repr(self.item)}.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' does not support 'in' operator.")


@constraint
class Unique:
    """Validates that all elements in a collection are unique."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
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


@constraint
class Email:
    """Validates an email address using a standard structural regex."""

    # A robust, reliable structural regex that catches the vast majority of email typos
    _regex = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+\Z")

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        try:
            if not self._regex.match(value):
                raise ValueError("Must be a valid email address.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as an email.")


@constraint
class StartsWith:
    prefix: str
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        try:
            if not value.startswith(self.prefix):
                raise ValueError(f"Must start with '{repr(self.prefix)}'")
        except (TypeError, AttributeError):
            raise TypeError(f"Type '{type(value).__name__}' does not support startswith().")


@constraint
class EndsWith:
    suffix: str
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        try:
            if not value.endswith(self.suffix):
                raise ValueError(f"Must end with '{repr(self.suffix)}'")
        except (TypeError, AttributeError):
            raise TypeError(f"Type '{type(value).__name__}' does not support endswith().")


@constraint
class UUID:
    """Validates that a value is a valid UUID string or object"""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if isinstance(value, uuid.UUID):
            return
        try:
            uuid.UUID(str(value))
        except ValueError:
            raise ValueError("Must be a valid UUID.")


@constraint
class URL:
    """Validates that a string is a properly formatted URL"""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        try:
            result = urlparse(str(value))
            if not all([result.scheme, result.netloc]):
                raise ValueError("Must be a valid URL.")
        except Exception:
            raise ValueError("Must be a valid URL.")


@constraint
class IPAddress:
    """Validates that a value is a valid IPv4 or IPv6 address"""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if isinstance(value, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            return
        try:
            ipaddress.ip_address(str(value))
        except ValueError:
            raise ValueError("Must be a valid IPv4 or IPv6 address.")


@constraint
class IsDir:
    """Validates that a string or Path object points to an existing directory."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        try:
            if not pathlib.Path(value).is_dir():
                raise ValueError("Must be an existing directory.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as a path.")


@constraint
class IsFile:
    """Validates that a string or Path object points to an existing file."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        try:
            if not pathlib.Path(value).is_file():
                raise ValueError("Must be an existing file.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as a path.")
