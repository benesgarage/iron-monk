import pytest
import datetime
import importlib
from typing import Annotated, Any, Generic, TypeVar

from monk import monk, validate, settings, constraint
from monk.exceptions import UnvalidatedAccessError, ValidationError
from monk.constraints import (
    Not,
    AnyOf,
    AllOf,
    StartsWith,
    LowerCase,
    IsUTC,
    Email,
    Interval,
    MultipleOf,
    Len,
    NotNull,
    IsAlpha,
    IsAlnum,
)
from monk.protocols import MonkConstraint


def test_validate_non_monk_object() -> None:
    with pytest.raises(TypeError):
        validate(123)


def test_structural_subtyping_duck_typing() -> None:
    class DuckConstraint:
        def validate(self, value: Any) -> None:
            pass

    assert isinstance(DuckConstraint(), MonkConstraint) is True


def test_not_inverter_constraint() -> None:
    constraint = Not(LowerCase)

    # Success (it is NOT lowercase)
    constraint.validate("HELLO")

    # Failure (it IS lowercase, so Not fails)
    with pytest.raises(ValueError):
        constraint.validate("hello")

    # Auto-instantiation failure
    with pytest.raises(TypeError, match="missing required arguments"):
        Not(MultipleOf)


def test_anyof_constraint() -> None:
    constraint = AnyOf(Email, StartsWith("+"))

    # Success paths
    constraint.validate("test@domain.com")
    constraint.validate("+123456789")

    # Failure path
    with pytest.raises(ValueError, match="Must satisfy at least one"):
        constraint.validate("invalid")

    # Custom message
    custom = AnyOf(Email, StartsWith("+"), message="Must be email or phone!")
    with pytest.raises(ValueError, match="Must be email or phone!"):
        custom.validate("invalid")

    # Initialization checks
    with pytest.raises(ValueError):
        AnyOf()
    with pytest.raises(TypeError, match="missing required arguments"):
        AnyOf(MultipleOf)


def test_allof_constraint() -> None:
    constraint = AllOf(LowerCase, Len(min_len=3))

    # Success
    constraint.validate("abc")

    # Failures (bubbles up the specific error)
    with pytest.raises(ValueError, match="islower"):
        constraint.validate("ABC")
    with pytest.raises(ValueError, match="minimum length"):
        constraint.validate("ab")

    # Custom message overrides specific errors
    custom = AllOf(LowerCase, Len(min_len=3), message="Invalid code format.")
    with pytest.raises(ValueError, match="Invalid code format."):
        custom.validate("ab")

    # Initialization checks
    with pytest.raises(ValueError):
        AllOf()
    with pytest.raises(TypeError, match="missing required arguments"):
        AllOf(MultipleOf)


def test_nested_logical_composability() -> None:
    # A complex rule: Must be an Email OR (Start with "+" AND be exactly/max 10 chars long)
    constraint = AnyOf(Email, AllOf(StartsWith("+"), Len(max_len=10)))

    # 1. Matches Email
    constraint.validate("test@domain.com")

    # 2. Matches the AllOf block
    constraint.validate("+123456789")

    # 3. Fails the AllOf block (starts with +, but too long) and fails Email
    with pytest.raises(ValueError, match="Must satisfy at least one"):
        constraint.validate("+12345678901")

    # 4. Fails both entirely
    with pytest.raises(ValueError, match="Must satisfy at least one"):
        constraint.validate("invalid")


def test_is_utc_constraint() -> None:
    dt_utc = datetime.datetime.now(datetime.timezone.utc)
    dt_naive = datetime.datetime.now()
    dt_other = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2)))

    IsUTC.validate(dt_utc)
    with pytest.raises(ValueError):
        IsUTC.validate(dt_naive)
    with pytest.raises(ValueError):
        IsUTC.validate(dt_other)


def test_is_alpha_alnum() -> None:
    IsAlpha.validate("abc")
    with pytest.raises(ValueError):
        IsAlpha.validate("abc1")

    IsAlnum.validate("abc1")
    with pytest.raises(ValueError):
        IsAlnum.validate("abc1!")


def test_trimmed_constraint() -> None:
    from monk.constraints import Trimmed

    Trimmed().validate("hello world")

    with pytest.raises(ValueError):
        Trimmed().validate(" hello")
    with pytest.raises(ValueError):
        Trimmed().validate("world ")

    with pytest.raises(TypeError):
        Trimmed().validate(123)


def test_past_future_constraints() -> None:
    from monk.constraints import Past, Future

    now = datetime.datetime.now()
    past_dt = now - datetime.timedelta(days=1)
    past_date = datetime.date.today() - datetime.timedelta(days=1)
    future_dt = now + datetime.timedelta(days=1)
    future_date = datetime.date.today() + datetime.timedelta(days=1)

    Past().validate(past_dt)
    Future().validate(future_dt)
    Past().validate(datetime.date.today() - datetime.timedelta(days=1))
    Future().validate(datetime.date.today() + datetime.timedelta(days=1))

    with pytest.raises(ValueError, match="Must be in the past"):
        Past().validate(future_dt)
    with pytest.raises(ValueError, match="Must be in the past"):
        Past().validate(future_date)
    with pytest.raises(ValueError, match="Must be in the future"):
        Future().validate(past_dt)
    with pytest.raises(ValueError, match="Must be in the future"):
        Future().validate(past_date)
    with pytest.raises(TypeError, match="cannot be evaluated as a date/time"):
        Past().validate("2024-01-01")
    with pytest.raises(TypeError, match="cannot be evaluated as a date/time"):
        Future().validate("2024-01-01")


@monk(slots=True)
class SlottedUser:
    username: Annotated[str, LowerCase]


def test_slotted_dataclass_lifecycle() -> None:
    user = SlottedUser(username="johndoe")

    # Prove that slots are actively restricting the object (no __dict__)
    assert not hasattr(user, "__dict__")

    # Prove access restriction still works
    with pytest.raises(UnvalidatedAccessError):
        _ = user.username

    validated_user = validate(user)
    assert validated_user.username == "johndoe"


@monk(slots=True)
class NoAnnotationsUser:
    username = None


def test_no_annotations() -> None:
    """Ensure a monk object with no annotations still inits successfully"""
    user = NoAnnotationsUser()

    with pytest.raises(UnvalidatedAccessError):
        _ = user.username

    validated_user = validate(user)
    assert validated_user.username is None


@monk(defer=False)
class InstantValidatedUser:
    email: Annotated[str, Email]


def test_defer_kwarg() -> None:
    # 1. Prove it fails instantly on bad data
    with pytest.raises(ValidationError):
        InstantValidatedUser(email="bad-email")

    # 2. Prove it is instantly uncloaked/accessible on valid data
    user = InstantValidatedUser(email="test@domain.com")
    assert user.email == "test@domain.com"


@monk
class GlobalConfigUser:
    email: Annotated[str, Email]


def test_global_config_defer() -> None:
    # Turn off deferred validation globally
    settings.defer = False

    with pytest.raises(ValidationError):
        GlobalConfigUser(email="bad-email")

    # Reset config so it doesn't bleed into other tests!
    settings.defer = True


def test_env_var_global_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the environment variable correctly toggles the configuration."""
    monkeypatch.setenv("MONK_DEFER", "false")
    monkeypatch.setenv("MONK_DEFAULT_ALLOW_NONE", "true")

    import monk.config

    importlib.reload(monk.config)  # Reload the file so the top-level 'if' statement runs again
    assert monk.config.settings.defer is False
    assert monk.config.settings.default_allow_none is True

    # Clean up and restore state
    monkeypatch.delenv("MONK_DEFER")
    monkeypatch.delenv("MONK_DEFAULT_ALLOW_NONE")
    importlib.reload(monk.config)


def test_repr_behavior() -> None:
    """Ensure printing an unvalidated object doesn't crash and shows the guarded state."""

    @monk
    class ReprUser:
        name: str

    user = ReprUser(name="Kai")

    # Before validation: should show the safe, patched repr
    assert "ReprUser" in repr(user) and "Kai" not in repr(user)

    # After validation: should return to the standard dataclass repr
    validated = validate(user)
    assert "ReprUser" in repr(validated) and "Kai" in repr(validated)


def test_constraint_auto_instantiation() -> None:
    class StatelessConstraint:
        def validate(self, value: Any) -> None:
            if value != "secret":
                raise ValueError("Must be secret.")

    @monk
    class Agent:
        password: Annotated[str, StatelessConstraint]  # No parenthesis

    # Prove it validates correctly
    validate(Agent(password="secret"))

    with pytest.raises(ValidationError):
        validate(Agent(password="password123"))


def test_constraint_auto_instantiation_missing_args() -> None:
    @constraint
    class StatefulConstraint:
        required_arg: int

        def validate(self, value: Any) -> None:
            pass

    # Ensure the decorator intercepts the missing arguments during class creation
    with pytest.raises(TypeError):

        @monk
        class FaultyAgent:  # pyright: ignore[reportUnusedClass]
            password: Annotated[str, StatefulConstraint]


def test_custom_error_messages() -> None:
    # 1. Test interpolation of constraint attributes and the bad value
    age_rule = Interval(ge=18, message="You must be at least {ge} years old. You provided {value}.")
    with pytest.raises(ValueError, match="You must be at least 18 years old. You provided 15."):
        age_rule.validate(15)

    # 2. Test fallback when format string has missing keys (prevents crash)
    bad_rule = Interval(ge=18, message="Missing {unknown_key} and {value}")
    with pytest.raises(ValueError, match="Missing {unknown_key} and {value}"):
        bad_rule.validate(15)

    # 3. Test on a standard constraint without parameters
    email_rule = Email(message="'{value}' is definitely not a corporate email.")
    with pytest.raises(ValueError, match="'bad-email' is definitely not a corporate email."):
        email_rule.validate("bad-email")

    # 4. Test nested interpolation (interpolating properties of an inner constraint)
    nested_rule = Not(
        Interval(ge=5, le=10),
        message="You picked {value}, but numbers between {constraint.ge} and {constraint.le} are forbidden!",
    )
    with pytest.raises(ValueError, match="You picked 7, but numbers between 5 and 10 are forbidden!"):
        nested_rule.validate(7)


def test_validation_error_flatten() -> None:
    @monk
    class TestModel:
        age: Annotated[int, Interval(ge=18)]

    try:
        validate(TestModel(age=12))
    except ValidationError as e:
        assert e.flatten() == ["age: Must be greater than or equal to 18."]


def test_validation_error_rfc7807() -> None:
    @monk
    class TestModel:
        age: Annotated[int, Interval(ge=18)]

    try:
        validate(TestModel(age=12))
    except ValidationError as e:
        rfc = e.to_rfc7807(instance="/api/users")
        assert rfc["status"] == 400
        assert rfc["instance"] == "/api/users"
        assert rfc["errors"][0]["field"] == "age"


def test_custom_error_codes() -> None:
    @monk
    class ErrorCodeModel:
        age: Annotated[int, Interval(ge=18)]  # Should default to "Interval"
        pin: Annotated[str, Len(min_len=4, code="INVALID_PIN")]  # Custom code

    with pytest.raises(ValidationError) as exc:
        validate(ErrorCodeModel(age=15, pin="12"))

    errors = exc.value.errors
    assert errors[0]["field"] == "age"
    assert errors[0]["code"] == "Interval"
    assert errors[1]["field"] == "pin"
    assert errors[1]["code"] == "INVALID_PIN"


def test_explicit_nullability() -> None:
    @monk
    class RequiredModel:
        # Strictly Required. Passing None will fail with NotNull!
        email: Annotated[str, Email]

        # Top-Level Optional. Passing None is safe.
        age: Annotated[int, Interval(ge=18)] | None = None

    with pytest.raises(ValidationError) as exc:
        validate(RequiredModel(email=None))  # type: ignore

    errors = exc.value.errors
    assert len(errors) == 1
    assert errors[0]["field"] == "email"
    assert errors[0]["code"] == "NotNull"

    # Succeeding explicit nullable
    validate(RequiredModel(email="test@domain.com", age=None))

    # Succeeding explicit nullable with an actual value (covers skipping the marker in operations.py)
    validate(RequiredModel(email="test@domain.com", age=25))


def test_global_allow_none_by_default() -> None:
    # Change the global setting so fields are nullable by default
    settings.default_allow_none = True

    @monk
    class LaxModel:
        age: Annotated[int, NotNull, Interval(ge=18)]
        email: Annotated[str | None, Email] = None

    # email passes because default_allow_none is True
    with pytest.raises(ValidationError) as exc:
        validate(LaxModel(age=None))  # type: ignore

    errors = exc.value.errors
    assert len(errors) == 1
    assert errors[0]["field"] == "age"
    assert errors[0]["code"] == "NotNull"

    # Reset for other tests
    settings.default_allow_none = False


def test_not_null_custom_message_and_code() -> None:
    @monk
    class CustomRequiredModel:
        email: Annotated[
            str,
            NotNull(message="We really need your email!", code="MISSING_EMAIL"),
            Email,
        ]

    with pytest.raises(ValidationError) as exc:
        validate(CustomRequiredModel(email=None))  # type: ignore

    errors = exc.value.errors
    assert len(errors) == 1
    assert errors[0]["field"] == "email"
    assert errors[0]["message"] == "We really need your email!"
    assert errors[0]["code"] == "MISSING_EMAIL"


def test_custom_post_init() -> None:
    @monk
    class PostInitModel:
        name: str

        def __post_init__(self) -> None:
            object.__setattr__(self, "custom_init_run", True)

    model = PostInitModel(name="test")
    assert object.__getattribute__(model, "custom_init_run") is True


def test_framework_wrapper_unwrapping() -> None:
    """Simulates SQLAlchemy's Mapped wrapper to ensure we extract inner constraints."""
    T_Wrap = TypeVar("T_Wrap")

    class Box(Generic[T_Wrap]):
        pass

    @monk
    class WrappedModel:
        email: Box[Annotated[str, Email]]

    with pytest.raises(ValidationError) as exc:
        validate(WrappedModel(email="bad-email"))  # type: ignore

    assert exc.value.errors[0]["code"] == "Email"


def test_invalid_monk_target() -> None:
    with pytest.raises(TypeError, match="Monk can only decorate classes or functions."):
        monk(123)  # type: ignore


def test_async_validate_rejection() -> None:
    @monk(defer=True)
    class AsyncUser:
        username: str

        async def __monk_validate__(self) -> str | None:
            return "bad"

    with pytest.raises(TypeError, match="iron-monk is strictly synchronous"):
        validate(AsyncUser(username="admin"))


def test_ignored_metadata_in_annotated() -> None:
    @monk
    class MetadataModel:
        # "just some string" is not a MonkConstraint, so it should be safely ignored
        value: Annotated[str, "just some string metadata"]

    # Should not crash and should resolve values perfectly
    assert validate(MetadataModel(value="test")).value == "test"


def test_validate_stream_item_failures() -> None:
    from monk.operations import validate_stream
    from monk.constraints import LowerCase, Nullable

    # 1. Test None value rejection
    gen = validate_stream(["a", None], LowerCase)
    assert next(gen) == "a"
    with pytest.raises(ValidationError) as exc:
        next(gen)
    assert exc.value.errors[0]["code"] == "NotNull"
    assert exc.value.errors[0]["field"] == "[1]"

    # 2. Test actual validation failure
    gen2 = validate_stream(["a", "B"], LowerCase)
    assert next(gen2) == "a"
    with pytest.raises(ValidationError) as exc2:
        next(gen2)
    assert exc2.value.errors[0]["code"] == "Predicate"
    assert exc2.value.errors[0]["field"] == "[1]"

    # 3. Test Nullable marker allowing None in stream
    gen3 = validate_stream(["a", None], Nullable, LowerCase)
    assert next(gen3) == "a"
    assert next(gen3) is None


def test_validate_stream_missing_constraint_args() -> None:
    from monk.operations import validate_stream
    from monk.constraints import MultipleOf

    # Len requires arguments, so passing the uninstantiated class should raise a TypeError
    with pytest.raises(TypeError, match="missing required arguments"):
        gen = validate_stream([6], MultipleOf)
        next(gen)  # The generator must be advanced to trigger preparation


def test_recurse_on_set() -> None:
    """Covers the set/frozenset branch in the _recurse helper."""

    @monk(frozen=True)  # Must be frozen to be hashable
    class Inner:
        val: Annotated[int, Interval(ge=10)]

        # Bypass dataclass tuple-hashing so we can safely add unvalidated objects to a set
        def __hash__(self) -> int:
            return id(self)

        def __eq__(self, other: Any) -> bool:
            return self is other

    @monk
    class Outer:
        items: set[Inner]

    # Success path (covers the recursion branch)
    validate(Outer(items={Inner(val=10), Inner(val=11)}))

    # Failure
    with pytest.raises(ValidationError) as exc:
        validate(Outer(items={Inner(val=10), Inner(val=9)}))

    assert exc.value.errors[0]["code"] == "Interval"


def test_function_validation_error_aggregation() -> None:
    """Covers the `except ValidationError` block in `validate_arguments`."""
    from monk.constraints import Each, LowerCase

    @monk
    def process_tags(tags: Annotated[list[str], Each(LowerCase)]) -> None:
        pass

    with pytest.raises(ValidationError) as exc:
        process_tags(tags=["a", "B", "c", "D"])

    errors = exc.value.errors
    assert len(errors) == 2
    assert errors[0]["field"] == "tags[1]"
    assert errors[1]["field"] == "tags[3]"


def test_return_validation_aggregation_and_recursion() -> None:
    """Covers `except ValidationError` and `_recurse` in `validate_return`."""
    from monk.constraints import Each, LowerCase, Len

    @monk
    class Inner:
        val: Annotated[int, Interval(ge=10)]

    # Test 1: Aggregation via `except ValidationError`
    @monk
    def get_tags() -> Annotated[list[str], Each(LowerCase)]:
        return ["a", "B", "c", "D"]

    with pytest.raises(ValidationError) as exc1:
        get_tags()

    errors1 = exc1.value.errors
    assert len(errors1) == 2
    assert errors1[0]["field"] == "return[1]"
    assert errors1[1]["field"] == "return[3]"

    # Test 2: Recursion on return value
    @monk
    def get_items() -> Annotated[list[Inner], Len(min_len=1)]:
        return [Inner(val=10), Inner(val=9)]

    with pytest.raises(ValidationError) as exc2:
        get_items()

    errors2 = exc2.value.errors
    assert len(errors2) == 1
    assert errors2[0]["field"] == "return[1].val"
    assert errors2[0]["code"] == "Interval"


def test_return_validation_none_rejection() -> None:
    """Covers the `if value is None` block in `validate_return`."""
    from monk.constraints import Len

    @monk
    def get_name() -> Annotated[str, Len(min_len=2)]:
        return None  # type: ignore

    with pytest.raises(ValidationError) as exc:
        get_name()

    assert exc.value.errors[0]["code"] == "NotNull"
    assert exc.value.errors[0]["field"] == "return"

    @monk
    def get_nullable_name() -> Annotated[str, Len(min_len=2)] | None:
        return None

    assert get_nullable_name() is None


def test_argument_validation_none_rejection() -> None:
    """Covers the `if value is None` block in `validate_arguments`."""
    from monk.constraints import Len

    @monk
    def process_name(name: Annotated[str, Len(min_len=2)]) -> None:
        pass

    with pytest.raises(ValidationError) as exc:
        process_name(name=None)  # type: ignore

    assert exc.value.errors[0]["code"] == "NotNull"
    assert exc.value.errors[0]["field"] == "name"

    @monk
    def process_nullable_name(name: Annotated[str, Len(min_len=2)] | None) -> None:
        pass

    process_nullable_name(name=None)


def test_ignored_sentinels() -> None:
    """Covers global sentinel skipping for PATCH requests/GraphQL APIs."""

    class UnsetType:
        pass

    # Sentinels in libraries like Strawberry are singleton instances!
    UNSET = UnsetType()

    settings.ignored_sentinels = (UNSET,)

    @monk
    class PatchModel:
        # Resolves as Union[UnsetType, Annotated[str, Email]]
        email: UnsetType | Annotated[str, Email] = UNSET

    # Should completely bypass NotNull and Email checks because the value is the sentinel
    validate(PatchModel())

    from monk.operations import validate_dict, validate_stream
    from typing import TypedDict

    # 1. Cover validate_arguments
    @monk
    def process_email(email: UnsetType | Annotated[str, Email] = UNSET) -> None:
        pass

    process_email(email=UNSET)

    # 2. Cover validate_return
    @monk
    def get_email() -> UnsetType | Annotated[str, Email]:
        return UNSET

    get_email()

    # 3. Cover validate_dict
    class PatchDict(TypedDict):
        email: UnsetType | Annotated[str, Email]

    validate_dict({"email": UNSET}, PatchDict)

    # 4. Cover validate_stream
    gen = validate_stream([UNSET], Email)
    assert next(gen) is UNSET

    settings.ignored_sentinels = ()  # Cleanup


def test_value_unwrappers() -> None:
    """Covers global wrapper unpacking for framework wrappers like Strawberry's Some."""

    T_Some = TypeVar("T_Some")

    class Some(Generic[T_Some]):
        def __init__(self, value: T_Some):
            self.value = value

    settings.unwrappers = {Some: lambda x: x.value}

    # Cover the case where unwrappers is populated, but the value's type is not registered
    assert settings.unwrap("unregistered_string") == "unregistered_string"

    @monk
    class WrapperModel:
        email: Some[Annotated[str, Email]]

    # Valid inner value (remains wrapped securely after validation!)
    model = validate(WrapperModel(email=Some("test@domain.com")))
    assert isinstance(model.email, Some)
    assert model.email.value == "test@domain.com"

    # Invalid inner value
    with pytest.raises(ValidationError) as exc:
        validate(WrapperModel(email=Some("bad")))
    assert exc.value.errors[0]["code"] == "Email"

    settings.unwrappers = {}  # Cleanup


def test_union_branch_routing() -> None:
    """Proves that Union types act as routing boundaries, respecting specific constraints per type."""

    @monk
    class MixedModel:
        target: Annotated[str, Len(max_len=1)] | Annotated[int, Interval(gt=2)] | None = None

    # 1. Null branch (Safely bypassed because None is in the union)
    assert validate(MixedModel()).target is None

    # 2. String branch
    assert validate(MixedModel(target="A")).target == "A"
    with pytest.raises(ValidationError) as exc1:
        validate(MixedModel(target="AB"))
    assert "at least one" in exc1.value.errors[0]["message"]

    # 3. Int branch
    assert validate(MixedModel(target=3)).target == 3
    with pytest.raises(ValidationError) as exc2:
        validate(MixedModel(target=1))
    assert "at least one" in exc2.value.errors[0]["message"]


def test_union_branch_edge_cases() -> None:
    """Covers edge cases in Union extraction, such as unannotated branches, wrappers, Nullable, and NotNull."""
    from monk.constraints import Nullable, NotNull

    T_Some = TypeVar("T_Some")

    class Some(Generic[T_Some]):
        def __init__(self, value: T_Some):
            self.value = value

    settings.unwrappers = {Some: lambda x: x.value}

    @monk
    class EdgeCaseModel:
        wrapped_or_unannotated: int | Some[Annotated[str, Email]]
        explicit_nullable: int | Annotated[str, Nullable, Email]
        explicit_notnull: int | Annotated[str, NotNull, Email]

    # 1. Unannotated int branch
    assert (
        validate(
            EdgeCaseModel(wrapped_or_unannotated=123, explicit_nullable=1, explicit_notnull=2)
        ).wrapped_or_unannotated
        == 123
    )

    # 2. Wrapper branch
    model = validate(
        EdgeCaseModel(
            wrapped_or_unannotated=Some("test@domain.com"),
            explicit_nullable=1,
            explicit_notnull=2,
        )
    )

    assert not isinstance(model.wrapped_or_unannotated, int)
    assert model.wrapped_or_unannotated.value == "test@domain.com"

    settings.unwrappers = {}  # Cleanup
