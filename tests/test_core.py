import pytest
import datetime
import importlib
from typing import Annotated, Any, Generic, TypeVar

from monk import monk, validate, settings, constraint
from monk.exceptions import UnvalidatedAccessError, ValidationError
from monk.constraints import Not, LowerCase, IsUTC, Email, Interval, MultipleOf, Len, Nullable, NotNull
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


def test_is_utc_constraint() -> None:
    dt_utc = datetime.datetime.now(datetime.timezone.utc)
    dt_naive = datetime.datetime.now()
    dt_other = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2)))

    IsUTC.validate(dt_utc)
    with pytest.raises(ValueError):
        IsUTC.validate(dt_naive)
    with pytest.raises(ValueError):
        IsUTC.validate(dt_other)


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
        class FaultyAgent:
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
        age: Annotated[int | None, Nullable, Interval(ge=18)] = None

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
