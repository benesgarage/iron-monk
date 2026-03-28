import datetime
import ipaddress
import json
import math
import re
import uuid
from collections.abc import Iterable, Sized, Iterator
from dataclasses import field
from typing import Any, Callable, Annotated, cast
from urllib.parse import urlparse
import pathlib

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
class AnyOf:
    """Validates that a value satisfies at least one of the given constraints."""

    constraints: tuple[MonkConstraint, ...] = field(init=False, repr=False, compare=False)
    message: str | None = field(default=None, kw_only=True)
    code: str | None = field(default=None, kw_only=True)

    def __init__(self, *constraints: MonkConstraint | type[Any], message: str | None = None, code: str | None = None):
        if not constraints:
            raise ValueError("AnyOf requires at least one constraint.")

        instantiated_constraints: list[MonkConstraint] = []
        for c in constraints:
            if isinstance(c, type) and issubclass(c, MonkConstraint):
                try:
                    instantiated_constraints.append(c())
                except TypeError as e:
                    raise TypeError(
                        f"Constraint '{c.__name__}' missing required arguments. Did you mean {c.__name__}(...)?"
                    ) from e
            else:
                instantiated_constraints.append(cast(MonkConstraint, c))

        object.__setattr__(self, "constraints", tuple(instantiated_constraints))
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "code", code)

    def validate(self, value: Any) -> None:
        for c in self.constraints:
            try:
                c.validate(value)
                return  # Passed at least one!
            except (ValueError, TypeError, ValidationError):
                continue

        raise ValueError("Must satisfy at least one of the provided constraints.")


@constraint
class AllOf:
    """Validates that a value satisfies all of the given constraints."""

    constraints: tuple[MonkConstraint, ...] = field(init=False, repr=False, compare=False)
    message: str | None = field(default=None, kw_only=True)
    code: str | None = field(default=None, kw_only=True)

    def __init__(self, *constraints: MonkConstraint | type[Any], message: str | None = None, code: str | None = None):
        if not constraints:
            raise ValueError("AllOf requires at least one constraint.")

        instantiated_constraints: list[MonkConstraint] = []
        for c in constraints:
            if isinstance(c, type) and issubclass(c, MonkConstraint):
                try:
                    instantiated_constraints.append(c())
                except TypeError as e:
                    raise TypeError(
                        f"Constraint '{c.__name__}' missing required arguments. Did you mean {c.__name__}(...)?"
                    ) from e
            else:
                instantiated_constraints.append(cast(MonkConstraint, c))

        object.__setattr__(self, "constraints", tuple(instantiated_constraints))
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "code", code)

    def validate(self, value: Any) -> None:
        for c in self.constraints:
            try:
                c.validate(value)
            except (ValueError, TypeError, ValidationError) as e:
                # If AllOf has a custom message, raise a standard ValueError so the @constraint decorator can format it
                if getattr(self, "message", None) is not None:
                    raise ValueError("Failed AllOf constraint.") from e
                raise


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
IsAlpha = Predicate(str.isalpha)
IsAlnum = Predicate(str.isalnum)

IsFinite = Predicate(math.isfinite)
IsNan = Predicate(math.isnan)
IsInfinite = Predicate(math.isinf)
NonNegative = Interval(ge=0)


def _is_utc(dt: datetime.datetime) -> bool:
    return dt.tzinfo is not None and dt.utcoffset() == datetime.timedelta(0)


IsUTC = Predicate(_is_utc)


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
        if isinstance(value, Iterator):
            raise TypeError(
                f"Cannot eagerly validate exhaustible iterator '{type(value).__name__}'. Use 'validate_stream()' for lazy validation, or convert to a list/tuple first."
            )

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
class Nested:
    """Validates a nested dictionary against a TypedDict or Dataclass schema."""

    schema: Any  # type | Callable[[], type]
    partial: bool = False
    message: str | None = None
    code: str | None = None
    _validate_fn: Any = field(default=None, init=False, repr=False, compare=False)
    _resolved_schema: Any = field(default=None, init=False, repr=False, compare=False)

    def validate(self, value: Any) -> None:
        if not isinstance(value, dict):
            raise TypeError(f"Type '{type(value).__name__}' is not a dictionary.")

        # Resolve lazy schemas once and cache them
        actual_schema = self._resolved_schema
        if actual_schema is None:
            actual_schema = self.schema
            if isinstance(actual_schema, str):
                raise TypeError(
                    f"String forward references ('{actual_schema}') are not supported in Nested. "
                    f"Use a lambda for recursive schemas: `Nested(lambda: {actual_schema})`."
                )
            if callable(actual_schema) and not isinstance(actual_schema, type):
                actual_schema = actual_schema()
            object.__setattr__(self, "_resolved_schema", actual_schema)

        # Local import cached to prevent massive hot-loop overhead
        validate_fn = self._validate_fn
        if validate_fn is None:
            from .operations import validate_dict

            validate_fn = validate_dict
            object.__setattr__(self, "_validate_fn", validate_fn)

        try:
            validate_fn(value, cast(type, actual_schema), partial=self.partial)
        except ValidationError as e:
            # Adjust the error paths so they concatenate via dot-notation
            for err in e.errors:
                field = err.get("field", "")
                if field and not field.startswith("["):
                    err["field"] = f".{field}"
            raise


@constraint
class Contains:
    """Validates that a collection or string contains a specific item/substring."""

    item: Any
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if isinstance(value, Iterator):
            raise TypeError(
                f"Cannot eagerly validate exhaustible iterator '{type(value).__name__}'. Use 'validate_stream()' for lazy validation, or convert to a list/tuple first."
            )

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
        if isinstance(value, Iterator):
            raise TypeError(
                f"Cannot eagerly validate exhaustible iterator '{type(value).__name__}'. Use 'validate_stream()' for lazy validation, or convert to a list/tuple first."
            )

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


@constraint
class Slug:
    """Validates a URL-safe slug (lowercase alphanumeric and hyphens)."""

    _regex = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\Z")
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        try:
            if not self._regex.match(value):
                raise ValueError("Must be a valid slug.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a slug.")


@constraint
class SemVer:
    """Validates standard Semantic Versioning."""

    _regex = re.compile(
        r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?\Z"
    )
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        try:
            if not self._regex.match(value):
                raise ValueError("Must be a valid semantic version.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a semantic version.")


@constraint
class Base64:
    """Validates a Base64 encoded string structurally."""

    _regex = re.compile(r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?\Z")
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        try:
            if not self._regex.match(value):
                raise ValueError("Must be a valid Base64 string.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as Base64.")


@constraint
class JSON:
    """Validates that a string can be safely parsed as JSON."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if not isinstance(value, str):
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as JSON.")
        try:
            json.loads(value)
        except ValueError:
            raise ValueError("Must be a valid JSON string.")


@constraint
class ContainsKeys:
    """Validates that a dictionary contains all the specified keys."""

    keys: Iterable[Any]
    _required_keys: frozenset[Any] = field(init=False, repr=False, compare=False)
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "_required_keys", frozenset(self.keys))

    def validate(self, value: Any) -> None:
        if not isinstance(value, dict):
            raise TypeError(f"Type '{type(value).__name__}' is not a dictionary.")
        missing = self._required_keys - value.keys()
        if missing:
            missing_str = ", ".join(repr(k) for k in missing)
            raise ValueError(f"Dictionary is missing required keys: {missing_str}")


@constraint
class Subset:
    """Validates that all elements in a collection are within a predefined set of choices."""

    choices: Iterable[Any]
    _allowed: frozenset[Any] = field(init=False, repr=False, compare=False)
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "_allowed", frozenset(self.choices))

    def validate(self, value: Any) -> None:
        if isinstance(value, Iterator):
            raise TypeError(
                f"Cannot eagerly validate exhaustible iterator '{type(value).__name__}'. Use 'validate_stream()' for lazy validation, or convert to a list/tuple first."
            )
        try:
            if not set(value).issubset(self._allowed):
                raise ValueError("Contains unallowed items.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' is not iterable.")


@constraint
class ExactLen:
    """Validates that a sized collection or string is exactly a specific length."""

    length: Annotated[int, NonNegative]
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        NonNegative.validate(self.length)

    def validate(self, value: Any) -> None:
        try:
            if len(value) != self.length:
                raise ValueError(f"Must have an exact length of {self.length}.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' does not support len().")


@constraint
class Trimmed:
    """Validates that a string has no leading or trailing whitespace."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if not isinstance(value, str):
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated for whitespace.")
        if value != value.strip():
            raise ValueError("Must not contain leading or trailing whitespace.")


@constraint
class IsISO8601:
    """Validates that a string is a valid ISO 8601 date or datetime."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if not isinstance(value, str):
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as an ISO 8601 string.")
        try:
            datetime.datetime.fromisoformat(value)
        except ValueError:
            raise ValueError("Must be a valid ISO 8601 string.")


@constraint
class Past:
    """Validates that a datetime or date is in the past."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if isinstance(value, datetime.datetime):
            now = datetime.datetime.now(value.tzinfo) if value.tzinfo else datetime.datetime.now()
            if value >= now:
                raise ValueError("Must be in the past.")
        elif isinstance(value, datetime.date):
            if value >= datetime.date.today():
                raise ValueError("Must be in the past.")
        else:
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as a date/time.")


@constraint
class Future:
    """Validates that a datetime or date is in the future."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if isinstance(value, datetime.datetime):
            now = datetime.datetime.now(value.tzinfo) if value.tzinfo else datetime.datetime.now()
            if value <= now:
                raise ValueError("Must be in the future.")
        elif isinstance(value, datetime.date):
            if value <= datetime.date.today():
                raise ValueError("Must be in the future.")
        else:
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as a date/time.")


@constraint
class HexColor:
    """Validates a hexadecimal color string (e.g., #FFF, #123456)."""

    _regex = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\Z")
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        try:
            if not self._regex.match(value):
                raise ValueError("Must be a valid hexadecimal color code.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a hex color.")


@constraint
class LatLong:
    """Validates a tuple or list of exactly two floats: (latitude, longitude)."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if not isinstance(value, (tuple, list)):
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as coordinates.")
        if len(value) != 2:
            raise ValueError("Must contain exactly two elements (latitude, longitude).")

        lat, lon = value
        if (
            not isinstance(lat, (int, float))
            or isinstance(lat, bool)
            or not isinstance(lon, (int, float))
            or isinstance(lon, bool)
        ):
            raise TypeError("Latitude and longitude must be numbers.")

        if not (-90.0 <= lat <= 90.0):
            raise ValueError("Latitude must be between -90 and 90 degrees.")
        if not (-180.0 <= lon <= 180.0):
            raise ValueError("Longitude must be between -180 and 180 degrees.")


@constraint
class Port:
    """Validates a standard network port number (1-65535)."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a port.")
        if not (1 <= value <= 65535):
            raise ValueError("Must be a valid port number (1-65535).")


@constraint
class MacAddress:
    """Validates a standard MAC address (e.g., 00:1A:2B:3C:4D:5E)."""

    _regex = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})\Z")
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        try:
            if not self._regex.match(value):
                raise ValueError("Must be a valid MAC address.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a MAC address.")


class CSV:
    """Validates a delimited string and applies constraints to each extracted element."""

    def __init__(
        self,
        *constraints: Any,
        separator: str = ",",
        unique: bool = False,
        message: str | None = None,
        code: str | None = None,
    ) -> None:
        self.separator = separator
        self.unique = unique
        self.message = message
        self.code = code
        # Safely instantiate any uninstantiated classes (e.g., LowerCase vs LowerCase())
        self._prepared = [c() if isinstance(c, type) else c for c in constraints]

    def validate(self, value: Any) -> None:
        if not isinstance(value, str):
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as a CSV string.")

        if not value:
            return

        errors: list[ErrorDict] = []
        seen: set[str] = set()

        for i, val in enumerate(value.split(self.separator)):
            if self.unique:
                if val in seen:
                    errors.append({"field": f"[{i}]", "message": "All elements must be unique.", "code": "Unique"})
                else:
                    seen.add(val)

            for c in self._prepared:
                try:
                    c.validate(val)
                except ValidationError as e:
                    for err in e.errors:
                        err["field"] = f"[{i}]{err.get('field', '')}"
                        errors.append(err)
                except (ValueError, TypeError) as e:
                    error_code = getattr(c, "code", None) or type(c).__name__
                    errors.append({"field": f"[{i}]", "message": str(e), "code": error_code})

        if errors:
            raise ValidationError(errors)


@constraint(kw_only=True)
class DictOf:
    """Validates arbitrary dictionaries by applying constraints to their keys and/or values."""

    key: Any = None
    value: Any = None
    message: str | None = None
    code: str | None = None

    _key_constraints: tuple[MonkConstraint, ...] = field(init=False, repr=False, compare=False)
    _value_constraints: tuple[MonkConstraint, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        def _prep(c_input: Any) -> tuple[MonkConstraint, ...]:
            if c_input is None:
                return ()
            c_list = c_input if isinstance(c_input, Iterable) and not isinstance(c_input, (str, bytes)) else [c_input]
            prepared: list[MonkConstraint] = []
            for c in c_list:
                if isinstance(c, type) and issubclass(c, MonkConstraint):
                    try:
                        prepared.append(c())
                    except TypeError as e:
                        raise TypeError(
                            f"Constraint '{c.__name__}' missing required arguments. Did you mean {c.__name__}(...)?"
                        ) from e
                else:
                    prepared.append(cast(MonkConstraint, c))
            return tuple(prepared)

        object.__setattr__(self, "_key_constraints", _prep(self.key))
        object.__setattr__(self, "_value_constraints", _prep(self.value))

    def validate(self, data: Any) -> None:
        if not isinstance(data, dict):
            raise TypeError(f"Type '{type(data).__name__}' is not a dictionary.")

        errors: list[ErrorDict] = []
        for k, v in data.items():
            if self._key_constraints:
                for c in self._key_constraints:
                    try:
                        c.validate(k)
                    except ValidationError as e:
                        for err in e.errors:
                            err["field"] = f"<key: {repr(k)}>{err.get('field', '')}"
                            errors.append(err)
                    except (ValueError, TypeError) as e:
                        error_code = getattr(c, "code", None) or type(c).__name__
                        errors.append({"field": f"<key: {repr(k)}>", "message": str(e), "code": error_code})

            if self._value_constraints:
                for c in self._value_constraints:
                    try:
                        c.validate(v)
                    except ValidationError as e:
                        for err in e.errors:
                            err["field"] = f"[{repr(k)}]{err.get('field', '')}"
                            errors.append(err)
                    except (ValueError, TypeError) as e:
                        error_code = getattr(c, "code", None) or type(c).__name__
                        errors.append({"field": f"[{repr(k)}]", "message": str(e), "code": error_code})

        if errors:
            raise ValidationError(errors)
