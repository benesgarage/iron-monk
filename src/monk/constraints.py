import datetime
import math
import re
from collections.abc import Iterable, Sized, Iterator
from dataclasses import field
from typing import Any, Callable, Annotated, cast

from .protocols import MonkConstraint, SupportsGt, SupportsGe, SupportsLt, SupportsLe, SupportsMod
from .decorators import constraint
from .exceptions import ValidationError
from .types import ErrorDict
from .config import settings
from .operations import _format_constraint_message  # pyright: ignore[reportPrivateUsage]


class _EachFastPathFail(Exception):
    """Internal sentinel raised when Each's optimistic fast path encounters
    a None item that is not allowed. Triggers fallback to the slow path."""

    __slots__ = ()


_SWITCH_MISSING: Any = object()


def _ensure_str(value: Any) -> str | None:
    """Coerces a string-like value to ``str``.

    Returns the value unchanged when it is already ``str``, decodes ``bytes`` /
    ``bytearray`` as UTF-8, and returns ``None`` for any other type — leaving
    the caller free to raise a context-specific ``TypeError``. Invalid UTF-8
    is a value problem, not a type problem, so it raises ``ValueError``.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("Bytes are not valid UTF-8.")
    return None


class Ref:
    """A marker used to reference another field dynamically."""

    __slots__ = ("field_name",)

    def __init__(self, field_name: str):
        self.field_name = field_name

    def __repr__(self) -> str:
        return f"Ref('{self.field_name}')"


class Ctx:
    """A marker used to reference a value from the validation context.

    Resolved at validation time from the ``context`` mapping passed to
    ``validate()``, ``validate_dict()``, or ``instance.validate()``. If the
    mapping is missing the key, a ``ValidationError`` is raised on the
    enclosing field. If no context was provided at all, a
    ``MissingContextError`` is raised (programmer error).

    Example:
        from typing import Annotated
        from monk import monk, validate
        from monk.constraints import Interval, Ctx

        @monk
        class AgeGate:
            age: Annotated[int, Interval(gte=Ctx("min_age"))]

        validate(AgeGate(age=15), context={"min_age": 18})  # raises
    """

    __slots__ = ("key",)

    def __init__(self, key: str):
        self.key = key

    def __repr__(self) -> str:
        return f"Ctx('{self.key}')"


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

    constraints: tuple[MonkConstraint, ...] = field(init=False, repr=False)
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

    constraints: tuple[MonkConstraint, ...] = field(init=False, repr=False)
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
class When:
    """Conditional validation: applies `then` (or `else_`) based on a test against a Ref-resolved sibling field.

    `field` is typically a `Ref` to another field on the same model. At validation
    time, the blueprint compiler resolves the Ref and runs `test` against the
    resolved value. If `test` passes, `then` is applied to the current field's
    value; if `test` raises, `else_` (when provided) is applied instead.

    Example:
        @monk
        class Order:
            payment_method: str
            cc_number: Annotated[
                str | None,
                When(field=Ref("payment_method"), test=Eq("credit"), then=Len(min_len=16, max_len=16)),
            ]
    """

    field: Any
    test: MonkConstraint | type[Any]
    then: MonkConstraint | type[Any]
    else_: MonkConstraint | type[Any] | None = None
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.test, type) and issubclass(self.test, MonkConstraint):
            try:
                object.__setattr__(self, "test", self.test())
            except TypeError as e:
                raise TypeError(
                    f"Constraint '{self.test.__name__}' missing required arguments. Did you mean {self.test.__name__}(...)?"
                ) from e
        if isinstance(self.then, type) and issubclass(self.then, MonkConstraint):
            try:
                object.__setattr__(self, "then", self.then())
            except TypeError as e:
                raise TypeError(
                    f"Constraint '{self.then.__name__}' missing required arguments. Did you mean {self.then.__name__}(...)?"
                ) from e
        if self.else_ is not None and isinstance(self.else_, type) and issubclass(self.else_, MonkConstraint):
            try:
                object.__setattr__(self, "else_", self.else_())
            except TypeError as e:
                raise TypeError(
                    f"Constraint '{self.else_.__name__}' missing required arguments. Did you mean {self.else_.__name__}(...)?"
                ) from e

    def validate(self, value: Any) -> None:
        try:
            cast(MonkConstraint, self.test).validate(self.field)
        except (ValueError, TypeError, ValidationError):
            if self.else_ is not None:
                cast(MonkConstraint, self.else_).validate(value)
            return
        cast(MonkConstraint, self.then).validate(value)


@constraint
class Switch:
    """Branches validation by the value of a Ref-resolved sibling field.

    `cases` maps discriminator values to constraints. If the resolved value of
    `field` is a key in `cases`, that constraint is applied to the current
    field's value. Otherwise `default` is applied if provided; if no `default`
    is set, an unknown discriminator raises a ``ValueError``.

    Example:
        @monk
        class Notification:
            channel: str
            target: Annotated[
                str,
                Switch(
                    field=Ref("channel"),
                    cases={"email": Email, "sms": Match(r"^\\+\\d+")},
                    default=Len(min_len=1),
                ),
            ]
    """

    field: Any
    cases: dict[Any, MonkConstraint | type[Any]]
    default: MonkConstraint | type[Any] | None = None
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        if not self.cases:
            raise ValueError("Switch requires at least one case.")

        new_cases: dict[Any, MonkConstraint] = {}
        for k, v in self.cases.items():
            if isinstance(v, type) and issubclass(v, MonkConstraint):
                try:
                    new_cases[k] = v()
                except TypeError as e:
                    raise TypeError(
                        f"Constraint '{v.__name__}' missing required arguments. Did you mean {v.__name__}(...)?"
                    ) from e
            else:
                new_cases[k] = cast(MonkConstraint, v)
        object.__setattr__(self, "cases", new_cases)

        if self.default is not None and isinstance(self.default, type) and issubclass(self.default, MonkConstraint):
            try:
                object.__setattr__(self, "default", self.default())
            except TypeError as e:
                raise TypeError(
                    f"Constraint '{self.default.__name__}' missing required arguments. Did you mean {self.default.__name__}(...)?"
                ) from e

    def validate(self, value: Any) -> None:
        try:
            constraint = self.cases.get(self.field, _SWITCH_MISSING)
        except TypeError:
            # Unhashable discriminator (e.g., dict/list). Treat as no match.
            constraint = _SWITCH_MISSING
        if constraint is _SWITCH_MISSING:
            if self.default is not None:
                self.default.validate(value)
                return
            raise ValueError(f"No case matches discriminator {self.field!r}.")
        cast(MonkConstraint, constraint).validate(value)


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


@constraint
class Eq:
    """Validates that a value is strictly equal to another value or Ref."""

    value: Any
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if value != self.value:
            raise ValueError(f"Must be equal to {self.value}.")


@constraint(kw_only=True)
class Interval:
    """Numeric or Comparable Interval bounds"""

    gt: SupportsGt | Ref | Ctx | None = None
    ge: SupportsGe | Ref | Ctx | None = None
    lt: SupportsLt | Ref | Ctx | None = None
    le: SupportsLe | Ref | Ctx | None = None
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
Positive = Interval(gt=0)
Negative = Interval(lt=0)


def _is_utc(dt: datetime.datetime) -> bool:
    return dt.tzinfo is not None and dt.utcoffset() == datetime.timedelta(0)


IsUTC = Predicate(_is_utc)


def _is_tz_aware(dt: Any) -> bool:
    return isinstance(dt, datetime.datetime) and dt.tzinfo is not None and dt.utcoffset() is not None


def _is_tz_naive(dt: Any) -> bool:
    return isinstance(dt, datetime.datetime) and (dt.tzinfo is None or dt.utcoffset() is None)


IsTzAware = Predicate(_is_tz_aware)
IsTzNaive = Predicate(_is_tz_naive)


@constraint
class Len:
    min_len: Annotated[int, NonNegative] | Ref | Ctx = 0
    max_len: Annotated[int | None, NonNegative] | Ref | Ctx = None
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.min_len, (Ref, Ctx)):
            NonNegative.validate(self.min_len)
        if self.max_len is not None and not isinstance(self.max_len, (Ref, Ctx)):
            NonNegative.validate(self.max_len)
            if not isinstance(self.min_len, (Ref, Ctx)) and self.min_len > self.max_len:
                raise ValueError(f"min_len ({self.min_len}) cannot be greater than max_len ({self.max_len}).")

    def validate(self, value: Any) -> None:
        try:
            length = len(value)
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' does not support len().")

        min_len = cast(int, self.min_len)
        max_len = cast(int | None, self.max_len)

        if length < min_len:
            raise ValueError(f"Must have a minimum length of {min_len}.")
        if max_len is not None and length > max_len:
            raise ValueError(f"Must have a maximum length of {max_len}.")


NonEmpty = Len(min_len=1)


@constraint
class MultipleOf:
    multiple_of: SupportsMod | Ref | Ctx
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.multiple_of, (Ref, Ctx)) and self.multiple_of == 0:
            raise ValueError("multiple_of cannot be 0.")

    def validate(self, value: Any) -> None:
        if self.multiple_of == 0:
            raise ValueError("multiple_of cannot be 0.")
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
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' does not support regex matching.")
        if not self._compiled.match(s):
            raise ValueError(f"Does not match the required pattern: {self.pattern}")


@constraint
class OneOf:
    """Validates that a value is an exact member of a predefined set of choices."""

    choices: Iterable[Any] | Ref | Ctx
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.choices, (Ref, Ctx)):
            import enum

            raw = self.choices
            if isinstance(raw, type) and issubclass(raw, enum.Enum):
                # Accept either the Enum member itself or its underlying value.
                members = list(raw)
                expanded: list[Any] = list(members)
                expanded.extend(m.value for m in members)
                object.__setattr__(self, "choices", tuple(expanded))
            else:
                # Always convert to tuple so the constraint is immutable and hashable (for tyro/FastAPI caching)
                object.__setattr__(self, "choices", tuple(raw))
            if not self.choices:
                raise ValueError("OneOf requires at least one choice.")

    def validate(self, value: Any) -> None:
        choices = cast(Iterable[Any], self.choices)
        if not choices:
            raise ValueError("OneOf requires at least one choice.")
        if value not in choices:
            allowed = ", ".join(repr(c) for c in choices)
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
        val_type = type(value)
        if val_type is not list and val_type is not tuple:
            if isinstance(value, Iterator):
                raise TypeError(
                    f"Cannot eagerly validate exhaustible iterator '{type(value).__name__}'. Use 'validate_stream()' for lazy validation, or convert to a list/tuple first."
                )
            if not isinstance(value, Iterable):
                raise TypeError(f"Type '{type(value).__name__}' is not iterable.")

        constraints = self.constraints
        allow_none = self.allow_none
        not_null_constraint = self.not_null_constraint
        unwrap = settings.unwrap

        # Optimistic single-constraint fast path: skip per-item try/except + enumerate.
        # On any failure, fall through to slow path that aggregates per-item errors.
        if len(constraints) == 1:
            c = constraints[0]
            fn = getattr(c, "_validate_inner", None) or c.validate
            try:
                if allow_none:
                    for item in value:
                        item = unwrap(item)
                        if item is None:
                            continue
                        fn(item)
                else:
                    for item in value:
                        item = unwrap(item)
                        if item is None:
                            raise _EachFastPathFail()
                        fn(item)
                return  # all items valid
            except (ValidationError, ValueError, TypeError, _EachFastPathFail):
                pass  # Fall through to slow path with full error tracking.

        errors: list[ErrorDict] = []
        for i, item in enumerate(value):
            item = unwrap(item)
            if item is None:
                if allow_none:
                    continue
                msg = getattr(not_null_constraint, "message", None) or "Field is required and cannot be null."
                code = getattr(not_null_constraint, "code", None) or "NotNull"
                errors.append({"field": f"[{i}]", "message": msg, "code": code})
                continue

            for c in constraints:
                fn = getattr(c, "_validate_inner", None) or c.validate
                try:
                    fn(item)
                except ValidationError as e:
                    for err in e.errors:
                        err["field"] = f"[{i}]{err.get('field', '')}"
                        errors.append(err)
                except (ValueError, TypeError) as e:
                    msg = _format_constraint_message(c, item, str(e))
                    error_code = getattr(c, "code", None) or type(c).__name__
                    errors.append({"field": f"[{i}]", "message": msg, "code": error_code})

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
    r"""Validates an email address using the HTML5 living-standard atom regex.

    Local-part accepts the full set of unquoted characters permitted by RFC 5322
    atoms (``a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-``), the same set used by the WHATWG
    HTML ``<input type="email">`` validator and most modern web forms. The domain
    must still be a dotted hostname (at least one ``.``) so single-label hosts
    like ``user@localhost`` are rejected — match what real mail servers accept.
    Quoted local parts and IP-literal domains (RFC 5321 §4.1.3) are
    intentionally out of scope; if you need them, compose ``AnyOf`` with a
    custom ``Match`` constraint.
    """

    _regex = re.compile(r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+\Z")

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as an email.")
        if not self._regex.match(s):
            raise ValueError("Must be a valid email address.")


@constraint
class StartsWith:
    prefix: str | Ref | Ctx
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' does not support startswith().")
        if not s.startswith(cast(str, self.prefix)):
            raise ValueError(f"Must start with '{repr(self.prefix)}'")


@constraint
class EndsWith:
    suffix: str | Ref | Ctx
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' does not support endswith().")
        if not s.endswith(cast(str, self.suffix)):
            raise ValueError(f"Must end with '{repr(self.suffix)}'")


@constraint
class UUID:
    """Validates that a value is a valid UUID string or object"""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        import uuid

        if isinstance(value, uuid.UUID):
            return
        try:
            uuid.UUID(str(value))
        except ValueError:
            raise ValueError("Must be a valid UUID.")


@constraint
class JWT:
    """Validates a JSON Web Token (JWT) structurally (Header.Payload.Signature)."""

    _regex = re.compile(r"^[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]*\Z")
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a JWT.")
        if not self._regex.match(s):
            raise ValueError("Must be a valid JSON Web Token (JWT).")


@constraint
class URL:
    """Validates that a string is a properly formatted URL"""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        from urllib.parse import urlparse

        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a URL.")
        try:
            result = urlparse(s)
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
        import ipaddress

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
        import pathlib

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
        import pathlib

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
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a slug.")
        if not self._regex.match(s):
            raise ValueError("Must be a valid slug.")


@constraint
class SemVer:
    """Validates standard Semantic Versioning."""

    _regex = re.compile(
        r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?\Z"
    )
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a semantic version.")
        if not self._regex.match(s):
            raise ValueError("Must be a valid semantic version.")


@constraint
class Base64:
    """Validates a Base64 encoded string structurally."""

    _regex = re.compile(r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?\Z")
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as Base64.")
        if not self._regex.match(s):
            raise ValueError("Must be a valid Base64 string.")


@constraint
class JSON:
    """Validates that a string can be safely parsed as JSON."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        import json

        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as JSON.")
        try:
            json.loads(s)
        except ValueError:
            raise ValueError("Must be a valid JSON string.")


@constraint
class ContainsKeys:
    """Validates that a dictionary contains all the specified keys."""

    keys: Iterable[Any] | Ref | Ctx
    _required_keys: frozenset[Any] = field(init=False, repr=False, compare=False)
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.keys, (Ref, Ctx)):
            object.__setattr__(self, "_required_keys", frozenset(self.keys))

    def validate(self, value: Any) -> None:
        if not isinstance(value, dict):
            raise TypeError(f"Type '{type(value).__name__}' is not a dictionary.")

        req_keys = getattr(self, "_required_keys", None)
        if req_keys is None:
            req_keys = frozenset(cast(Iterable[Any], self.keys))

        missing = req_keys - value.keys()
        if missing:
            missing_str = ", ".join(repr(k) for k in missing)
            raise ValueError(f"Dictionary is missing required keys: {missing_str}")


@constraint
class Subset:
    """Validates that all elements in a collection are within a predefined set of choices."""

    choices: Iterable[Any] | Ref | Ctx
    _allowed: frozenset[Any] = field(init=False, repr=False, compare=False)
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.choices, (Ref, Ctx)):
            object.__setattr__(self, "_allowed", frozenset(self.choices))

    def validate(self, value: Any) -> None:
        if isinstance(value, Iterator):
            raise TypeError(
                f"Cannot eagerly validate exhaustible iterator '{type(value).__name__}'. Use 'validate_stream()' for lazy validation, or convert to a list/tuple first."
            )

        allowed = getattr(self, "_allowed", None)
        if allowed is None:
            allowed = frozenset(cast(Iterable[Any], self.choices))

        try:
            if not set(value).issubset(allowed):
                raise ValueError("Contains unallowed items.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' is not iterable.")


@constraint
class ExactLen:
    """Validates that a sized collection or string is exactly a specific length."""

    length: Annotated[int, NonNegative] | Ref | Ctx
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.length, (Ref, Ctx)):
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
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated for whitespace.")
        if s != s.strip():
            raise ValueError("Must not contain leading or trailing whitespace.")


@constraint
class Blank:
    """Validates that a string is empty or contains only whitespace."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as blank.")
        if s.strip() != "":
            raise ValueError("Must be blank.")


@constraint
class IsISO8601:
    """Validates that a string is a valid ISO 8601 date or datetime."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as an ISO 8601 string.")
        try:
            datetime.datetime.fromisoformat(s)
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
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a hex color.")
        if not self._regex.match(s):
            raise ValueError("Must be a valid hexadecimal color code.")


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
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a MAC address.")
        if not self._regex.match(s):
            raise ValueError("Must be a valid MAC address.")


@constraint
class CSV:
    """Validates a delimited string and applies constraints to each extracted element."""

    separator: str = field(default=",", init=False)
    unique: bool = field(default=False, init=False)
    message: str | None = field(default=None, init=False)
    code: str | None = field(default=None, init=False)
    _prepared: list[MonkConstraint] = field(init=False, repr=False, compare=False)

    def __init__(
        self,
        *constraints: Any,
        separator: str = ",",
        unique: bool = False,
        message: str | None = None,
        code: str | None = None,
    ) -> None:
        object.__setattr__(self, "separator", separator)
        object.__setattr__(self, "unique", unique)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "code", code)
        # Safely instantiate any uninstantiated classes (e.g., LowerCase vs LowerCase())
        object.__setattr__(self, "_prepared", [c() if isinstance(c, type) else c for c in constraints])

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as a CSV string.")

        if not s:
            return

        errors: list[ErrorDict] = []
        seen: set[str] = set()

        for i, val in enumerate(s.split(self.separator)):
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
class Cron:
    """Validates a cron expression structurally (supports standard 5-field and AWS 6-field formats)."""

    allow_aws: bool = False
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a cron expression.")

        # Handle standard macros like @daily
        if not self.allow_aws and s.startswith("@"):
            if s not in ("@yearly", "@annually", "@monthly", "@weekly", "@daily", "@midnight", "@hourly"):
                raise ValueError("Invalid cron macro.")
            return

        parts = s.split()
        expected_len = 6 if self.allow_aws else 5

        if len(parts) != expected_len:
            format_name = "AWS (6-field)" if self.allow_aws else "Standard (5-field)"
            raise ValueError(f"Must be a valid {format_name} cron expression.")

        # A fast structural regex for a single cron field (handles numbers, ranges, steps, and AWS specific chars)
        field_regex = re.compile(r"^[\*0-9,\-/\?LWA-Za-z#]+$")
        for part in parts:
            if not field_regex.match(part):
                raise ValueError("Contains invalid cron characters.")

        if self.allow_aws:
            # AWS requires exactly one '?' in either Day-of-month (index 2) or Day-of-week (index 4)
            if (parts[2] == "?") == (parts[4] == "?"):
                raise ValueError("AWS cron requires exactly one '?' in either the Day-of-month or Day-of-week field.")


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

    def validate(self, value: Any) -> None:
        if not isinstance(value, dict):
            raise TypeError(f"Type '{type(value).__name__}' is not a dictionary.")

        errors: list[ErrorDict] = []
        for k, v in value.items():
            k = settings.unwrap(k)
            v = settings.unwrap(v)
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


@constraint
class PhoneE164:
    """Validates a phone number in E.164 structural format (e.g., +14155552671)."""

    _regex = re.compile(r"^\+[1-9]\d{1,14}\Z")
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a phone number.")
        if not self._regex.match(s):
            raise ValueError("Must be a valid E.164 phone number (e.g., +14155552671).")


@constraint
class MimeType:
    """Validates a MIME type per RFC 6838 (e.g., application/json, text/html; charset=utf-8)."""

    _regex = re.compile(
        r"^[a-zA-Z0-9!#$&^_.+-]+/[a-zA-Z0-9!#$&^_.+-]+"
        r"(\s*;\s*[a-zA-Z0-9!#$&^_.+-]+=(\"[^\"]*\"|[a-zA-Z0-9!#$&^_.+-]+))*\Z"
    )
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a MIME type.")
        if not self._regex.match(s):
            raise ValueError("Must be a valid MIME type (e.g., 'application/json').")


_HASH_LENGTHS: dict[str, int] = {
    "md5": 32,
    "sha1": 40,
    "sha224": 56,
    "sha256": 64,
    "sha384": 96,
    "sha512": 128,
    "blake2s": 64,
    "blake2b": 128,
}
_HEX_REGEX = re.compile(r"^[0-9a-fA-F]+\Z")


@constraint
class Hash:
    """Validates a hex-encoded hash digest of fixed length per algorithm.

    Supported algorithms: md5, sha1, sha224, sha256, sha384, sha512, blake2s, blake2b.
    """

    algorithm: str
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        algo = self.algorithm.lower()
        if algo not in _HASH_LENGTHS:
            raise ValueError(
                f"Unsupported hash algorithm '{self.algorithm}'. Expected one of: {', '.join(sorted(_HASH_LENGTHS))}."
            )
        object.__setattr__(self, "algorithm", algo)

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a hash digest.")
        expected = _HASH_LENGTHS[self.algorithm]
        if len(s) != expected or not _HEX_REGEX.match(s):
            raise ValueError(f"Must be a valid {self.algorithm} hex digest of length {expected}.")


@constraint
class CreditCard:
    """Validates a credit card number using Luhn checksum and length 13-19."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a credit card.")
        digits_str = s.replace(" ", "").replace("-", "")
        if not digits_str.isdigit() or not (13 <= len(digits_str) <= 19):
            raise ValueError("Must be a 13-19 digit credit card number.")
        checksum = 0
        for i, ch in enumerate(reversed(digits_str)):
            d = int(ch)
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            checksum += d
        if checksum % 10 != 0:
            raise ValueError("Must be a valid credit card number (Luhn checksum failed).")


@constraint
class ISBN:
    """Validates ISBN-10 or ISBN-13 with checksum verification."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as an ISBN.")
        cleaned = s.replace("-", "").replace(" ", "").upper()
        if len(cleaned) == 10:
            if not (cleaned[:9].isdigit() and (cleaned[9].isdigit() or cleaned[9] == "X")):
                raise ValueError("Must be a valid ISBN-10.")
            total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(cleaned))
            if total % 11 != 0:
                raise ValueError("Must be a valid ISBN-10 (checksum failed).")
        elif len(cleaned) == 13:
            if not cleaned.isdigit():
                raise ValueError("Must be a valid ISBN-13.")
            total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(cleaned[:12]))
            check = (10 - total % 10) % 10
            if check != int(cleaned[12]):
                raise ValueError("Must be a valid ISBN-13 (checksum failed).")
        else:
            raise ValueError("Must be a valid ISBN-10 or ISBN-13.")


def _is_real_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


@constraint
class NonZero:
    """Validates that a numeric value is not zero."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        try:
            if value == 0:
                raise ValueError("Must not be zero.")
        except TypeError:
            raise TypeError(f"Type '{type(value).__name__}' does not support comparison to zero.")


@constraint
class Even:
    """Validates that an integer is even."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if not _is_real_int(value):
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as even/odd.")
        if value % 2 != 0:
            raise ValueError("Must be an even integer.")


@constraint
class Odd:
    """Validates that an integer is odd."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if not _is_real_int(value):
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as even/odd.")
        if value % 2 == 0:
            raise ValueError("Must be an odd integer.")


@constraint
class PowerOfTwo:
    """Validates that a positive integer is a power of two (1, 2, 4, 8, ...)."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if not _is_real_int(value):
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as a power of two.")
        if value <= 0 or (value & (value - 1)) != 0:
            raise ValueError("Must be a positive power of two.")


@constraint
class HexString:
    """Validates that a string contains only hex characters (optionally of a fixed length)."""

    length: int | None = None
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        if self.length is not None and self.length < 1:
            raise ValueError("length must be a positive integer.")

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a hex string.")
        if not _HEX_REGEX.match(s):
            raise ValueError("Must contain only hexadecimal characters.")
        if self.length is not None and len(s) != self.length:
            raise ValueError(f"Must be exactly {self.length} hex characters.")


@constraint
class TimezoneName:
    """Validates that a string is a valid IANA timezone name (e.g., 'America/New_York')."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a timezone name.")
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(s)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Must be a valid IANA timezone name.")


@constraint
class Sorted:
    """Validates that an iterable is sorted (ascending by default, descending if reverse=True)."""

    reverse: bool = False
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if isinstance(value, Iterator):
            raise TypeError(
                f"Cannot eagerly validate exhaustible iterator '{type(value).__name__}'. "
                f"Use 'validate_stream()' for lazy validation, or convert to a list/tuple first."
            )
        if not isinstance(value, Iterable):
            raise TypeError(f"Type '{type(value).__name__}' is not iterable.")
        items = list(value)
        try:
            if self.reverse:
                for i in range(len(items) - 1):
                    if items[i] < items[i + 1]:
                        raise ValueError("Must be sorted in descending order.")
            else:
                for i in range(len(items) - 1):
                    if items[i] > items[i + 1]:
                        raise ValueError("Must be sorted in ascending order.")
        except TypeError:
            raise TypeError("Items in iterable do not support comparison.")


@constraint
class NoWhitespace:
    """Validates that a string contains no whitespace characters."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated for whitespace.")
        if any(c.isspace() for c in s):
            raise ValueError("Must not contain any whitespace characters.")


@constraint
class SingleLine:
    """Validates that a string contains no newline or carriage-return characters."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as a single-line string.")
        if "\n" in s or "\r" in s:
            raise ValueError("Must not contain newline characters.")


Printable = Predicate(str.isprintable)


@constraint
class MaxBytes:
    """Validates that a string's UTF-8 encoded length is at most `max_bytes`.

    Accepts ``str`` (encoded as UTF-8 to count) or raw ``bytes`` / ``bytearray``
    (counted directly). Useful for database column limits and API payload guards
    where char count diverges from byte count for multibyte characters (CJK,
    emoji, accented Latin).
    """

    max_bytes: int
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        if self.max_bytes < 1:
            raise ValueError("max_bytes must be a positive integer.")

    def validate(self, value: Any) -> None:
        if isinstance(value, str):
            n = len(value.encode("utf-8"))
        elif isinstance(value, (bytes, bytearray)):
            n = len(value)
        else:
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated for byte length.")
        if n > self.max_bytes:
            raise ValueError(f"Must encode to at most {self.max_bytes} UTF-8 bytes.")


@constraint
class PathSafe:
    """Validates a filename: no path separators, no `..` segments, no null bytes, not empty, not `.`/`..`."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated as a filename.")
        if not s:
            raise ValueError("Filename must not be empty.")
        if s in (".", ".."):
            raise ValueError("Filename must not be '.' or '..'.")
        if "/" in s or "\\" in s:
            raise ValueError("Filename must not contain path separators.")
        if "\x00" in s:
            raise ValueError("Filename must not contain null bytes.")


_HOSTNAME_REGEX = re.compile(
    r"^(?=.{1,253}\Z)([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)"
    r"(?:\.(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?))*\Z"
)


@constraint
class Hostname:
    """Validates an RFC 1123 hostname (labels 1-63 chars, alphanum + hyphen, total ≤253)."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a hostname.")
        if not _HOSTNAME_REGEX.match(s):
            raise ValueError("Must be a valid RFC 1123 hostname.")


@constraint
class HttpURL:
    """Validates a URL restricted to the http or https scheme."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        from urllib.parse import urlparse

        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a URL.")
        try:
            result = urlparse(s)
        except Exception:
            raise ValueError("Must be a valid HTTP(S) URL.")
        if result.scheme not in ("http", "https") or not result.netloc:
            raise ValueError("Must be an http:// or https:// URL.")


_DATA_URI_REGEX = re.compile(
    r"^data:"
    r"([a-zA-Z0-9!#$&^_.+-]+/[a-zA-Z0-9!#$&^_.+-]+)?"
    r"(;[a-zA-Z0-9!#$&^_.+-]+=[a-zA-Z0-9!#$&^_.+-]+)*"
    r"(;base64)?,.*\Z",
    re.DOTALL,
)


@constraint
class DataURI:
    """Validates a data URI per RFC 2397 (e.g., `data:image/png;base64,iVBORw0...`)."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a data URI.")
        if not _DATA_URI_REGEX.match(s):
            raise ValueError("Must be a valid data URI (e.g., 'data:image/png;base64,...').")


_TIME_OF_DAY_REGEX = re.compile(r"^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?\Z")


@constraint
class TimeOfDay:
    """Validates a 24-hour time-of-day string in `HH:MM` or `HH:MM:SS` format."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a time of day.")
        if not _TIME_OF_DAY_REGEX.match(s):
            raise ValueError("Must be a valid 24-hour time of day (HH:MM or HH:MM:SS).")


@constraint
class DecimalPlaces:
    """Validates that a numeric or numeric-string has at most `max_places` digits after the decimal point.

    Accepts `int`, `float`, `decimal.Decimal`, or a numeric string. Trailing zeros count as places
    (so `Decimal("1.50")` has 2 places).
    """

    max_places: int
    message: str | None = None
    code: str | None = None

    def __post_init__(self) -> None:
        if self.max_places < 0:
            raise ValueError("max_places must be non-negative.")

    def validate(self, value: Any) -> None:
        from decimal import Decimal

        if isinstance(value, bool):
            raise TypeError("Boolean values cannot be evaluated as decimals.")
        if isinstance(value, Decimal):
            exp = value.as_tuple().exponent
            places = -exp if isinstance(exp, int) and exp < 0 else 0
        elif isinstance(value, (int, float)):
            s = repr(value) if isinstance(value, float) else str(value)
            places = len(s.split(".", 1)[1]) if "." in s else 0
        elif isinstance(value, str):
            try:
                Decimal(value)
            except Exception:
                raise ValueError("Must be a valid decimal number.")
            cleaned = value.strip().lstrip("+-")
            if "e" in cleaned or "E" in cleaned:
                # Scientific notation: round-trip through Decimal for accurate place count.
                exp = Decimal(value).normalize().as_tuple().exponent
                places = -exp if isinstance(exp, int) and exp < 0 else 0
            else:
                places = len(cleaned.split(".", 1)[1]) if "." in cleaned else 0
        else:
            raise TypeError(f"Type '{type(value).__name__}' cannot be evaluated for decimal places.")

        if places > self.max_places:
            raise ValueError(f"Must have at most {self.max_places} decimal places.")


@constraint
class AllEqual:
    """Validates that every element in an iterable is equal to the others. Empty iterables pass."""

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if isinstance(value, Iterator):
            raise TypeError(
                f"Cannot eagerly validate exhaustible iterator '{type(value).__name__}'. "
                f"Use 'validate_stream()' for lazy validation, or convert to a list/tuple first."
            )
        if not isinstance(value, Iterable):
            raise TypeError(f"Type '{type(value).__name__}' is not iterable.")
        sentinel: Any = object()
        first: Any = sentinel
        for item in value:
            if first is sentinel:
                first = item
            elif item != first:
                raise ValueError("All elements must be equal.")


_PEM_BLOCK_REGEX = re.compile(
    r"^-----BEGIN ([A-Z][A-Z0-9 ]*)-----\s*"
    r"([A-Za-z0-9+/=\s]*?)\s*"
    r"-----END \1-----\s*\Z",
    re.DOTALL,
)


@constraint
class PEMBlock:
    """Structurally validates a PEM-encoded block (e.g., X.509 certificate, RSA key, SSH public key).

    Checks the `-----BEGIN <LABEL>-----` / `-----END <LABEL>-----` envelope and Base64 body.
    Performs **no cryptographic verification** — use a crypto library for that.
    """

    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        s = _ensure_str(value)
        if s is None:
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as a PEM block.")
        match = _PEM_BLOCK_REGEX.match(s)
        if not match:
            raise ValueError("Must be a valid PEM block with matching BEGIN/END labels.")
        body = match.group(2)
        if not body or not any(c.isalnum() or c in "+/=" for c in body):
            raise ValueError("PEM block body must contain at least one Base64 character.")


@constraint
class FileSize:
    """Validates that a ``bytes`` / ``bytearray`` value's length falls within ``[min_size, max_size]``.

    Intended for file-upload bodies. Both bounds are inclusive; either may be
    ``None`` to skip that side of the check. Unlike :class:`MaxBytes`, this
    does not accept ``str`` — mixing string byte-length and file-body length
    would hide bugs.
    """

    min_size: int | None = None
    max_size: int | None = None
    message: str | None = None
    code: str | None = None

    def validate(self, value: Any) -> None:
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as file size; expected bytes.")
        n = len(value)
        if self.min_size is not None and n < self.min_size:
            raise ValueError(f"File size {n} bytes is below minimum of {self.min_size} bytes.")
        if self.max_size is not None and n > self.max_size:
            raise ValueError(f"File size {n} bytes exceeds maximum of {self.max_size} bytes.")


_MagicPattern = tuple[tuple[bytes, int], ...]
_MagicRegistry = dict[str, tuple[_MagicPattern, ...]]

_DEFAULT_MAGIC_SIGNATURES: _MagicRegistry = {
    # Images
    "image/png": (((b"\x89PNG\r\n\x1a\n", 0),),),
    "image/jpeg": (((b"\xff\xd8\xff", 0),),),
    "image/gif": (((b"GIF87a", 0),), ((b"GIF89a", 0),)),
    "image/webp": (((b"RIFF", 0), (b"WEBP", 8)),),
    "image/bmp": (((b"BM", 0),),),
    "image/tiff": (((b"II*\x00", 0),), ((b"MM\x00*", 0),)),
    "image/x-icon": (((b"\x00\x00\x01\x00", 0),),),
    # Documents
    "application/pdf": (((b"%PDF-", 0),),),
    "application/rtf": (((b"{\\rtf", 0),),),
    # Archives (ZIP also covers DOCX/XLSX/PPTX by design — disambiguation is out of scope)
    "application/zip": (((b"PK\x03\x04", 0),), ((b"PK\x05\x06", 0),), ((b"PK\x07\x08", 0),)),
    "application/gzip": (((b"\x1f\x8b", 0),),),
    "application/x-tar": (((b"ustar", 257),),),
    "application/x-7z-compressed": (((b"7z\xbc\xaf\x27\x1c", 0),),),
    "application/vnd.rar": (((b"Rar!\x1a\x07\x00", 0),), ((b"Rar!\x1a\x07\x01\x00", 0),)),
    # Media
    "audio/mpeg": (((b"ID3", 0),), ((b"\xff\xfb", 0),), ((b"\xff\xf3", 0),), ((b"\xff\xf2", 0),)),
    "video/mp4": (((b"ftyp", 4),),),
    "audio/wav": (((b"RIFF", 0), (b"WAVE", 8)),),
    "audio/ogg": (((b"OggS", 0),),),
    "video/webm": (((b"\x1aE\xdf\xa3", 0),),),
    "video/x-msvideo": (((b"RIFF", 0), (b"AVI ", 8)),),
}


def _detect_mime(data: bytes | bytearray, registry: _MagicRegistry) -> str | None:
    """Returns the first mime whose signature matches ``data``, or ``None``."""
    mv = memoryview(data)
    n = len(mv)
    for mime, alternatives in registry.items():
        for pattern in alternatives:
            if all(n >= offset + len(sig) and bytes(mv[offset : offset + len(sig)]) == sig for sig, offset in pattern):
                return mime
    return None


@constraint
class MagicBytes:
    """Validates that a ``bytes`` value's content matches a known file-format signature.

    Sniffs the leading bytes of ``value`` against an internal registry of magic
    signatures and asserts the detected mime is in ``allowed`` (if provided).
    Defends against extension- and header-based mime spoofing.

    Supply ``extra_signatures`` to register custom formats. Each entry maps a
    mime string to a single AND-pattern (tuple of ``(bytes, offset)`` pairs that
    must all match).

    Allowed list uses **mime strings**, e.g. ``("image/png", "image/jpeg")``.
    A single mime string is also accepted as shorthand (e.g. ``allowed="image/png"``).
    When ``allowed=None``, any recognized format passes.

    ``allowed`` also accepts ``Ref("other_field")`` / ``Ctx("key")`` markers so
    the whitelist can be sourced from a sibling field or validation context. The
    resolved value may be either a single mime string or an iterable of strings.
    """

    allowed: Iterable[str] | str | Ref | Ctx | None = None
    extra_signatures: dict[str, _MagicPattern] | None = None
    message: str | None = None
    code: str | None = None

    _registry: _MagicRegistry = field(init=False, repr=False, compare=False)
    _allowed_set: frozenset[str] | None = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        registry: _MagicRegistry = dict(_DEFAULT_MAGIC_SIGNATURES)
        if self.extra_signatures:
            for mime, pattern in self.extra_signatures.items():
                registry[mime] = (pattern,)
        object.__setattr__(self, "_registry", registry)
        if isinstance(self.allowed, (Ref, Ctx)) or self.allowed is None:
            object.__setattr__(self, "_allowed_set", None)
        else:
            object.__setattr__(self, "_allowed_set", _coerce_allowed_mimes(self.allowed))

    def validate(self, value: Any) -> None:
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError(f"Type '{type(value).__name__}' cannot be validated as file content; expected bytes.")
        detected = _detect_mime(value, self._registry)
        if detected is None:
            raise ValueError("File content does not match any known file format signature.")
        allowed_set = self._allowed_set
        if allowed_set is None and self.allowed is not None and not isinstance(self.allowed, (Ref, Ctx)):
            # ``allowed`` was a Ref/Ctx at decoration time; the blueprint cloner has
            # since overwritten it with the resolved sibling/context value. Build the
            # whitelist from that resolved value now.
            allowed_set = _coerce_allowed_mimes(self.allowed)
        if allowed_set is not None and detected not in allowed_set:
            allowed_str = ", ".join(sorted(allowed_set))
            raise ValueError(f"Detected file type '{detected}' is not in allowed types: {allowed_str}.")


def _coerce_allowed_mimes(allowed: Any) -> frozenset[str]:
    """Normalises a ``MagicBytes.allowed`` value into a ``frozenset[str]``.

    Accepts a single mime string (wrapped into a single-element set) or any
    iterable of mime strings. Raises ``TypeError`` for other shapes so misuse is
    caught at construction time (or, for Ref/Ctx-sourced values, at validation
    time) rather than producing silently empty whitelists.
    """
    if isinstance(allowed, str):
        return frozenset((allowed,))
    if isinstance(allowed, Iterable):
        return frozenset(allowed)
    raise TypeError(
        f"MagicBytes(allowed=...) expected a mime string or iterable of mime strings, got '{type(allowed).__name__}'."
    )
