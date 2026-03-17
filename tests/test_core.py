import pytest
import datetime
import importlib
from typing import Annotated, Any

from monk import monk, validate, settings, constraint
from monk.exceptions import UnvalidatedAccessError, ValidationError
from monk.constraints import Not, LowerCase, IsUTC, Email
from monk.protocols import MonkConstraint


def test_validate_non_monk_object() -> None:
    with pytest.raises(TypeError):
        validate(123)


def test_structural_subtyping_duck_typing() -> None:
    class DuckConstraint:
        def validate(self, field: str, value: Any) -> None:
            pass

    assert isinstance(DuckConstraint(), MonkConstraint) is True


def test_not_inverter_constraint() -> None:
    constraint = Not(LowerCase)

    # Success (it is NOT lowercase)
    constraint.validate("word", "HELLO")
    constraint.validate("word", None)

    # Failure (it IS lowercase, so Not fails)
    with pytest.raises(ValueError):
        constraint.validate("word", "hello")


def test_is_utc_constraint() -> None:
    dt_utc = datetime.datetime.now(datetime.timezone.utc)
    dt_naive = datetime.datetime.now()
    dt_other = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2)))

    IsUTC.validate("dt", dt_utc)
    IsUTC.validate("dt", None)
    with pytest.raises(ValueError):
        IsUTC.validate("dt", dt_naive)
    with pytest.raises(ValueError):
        IsUTC.validate("dt", dt_other)


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


@monk(deferred_validation=False)
class InstantValidatedUser:
    email: Annotated[str, Email]


def test_deferred_validation_kwarg() -> None:
    # 1. Prove it fails instantly on bad data
    with pytest.raises(ValidationError):
        InstantValidatedUser(email="bad-email")

    # 2. Prove it is instantly uncloaked/accessible on valid data
    user = InstantValidatedUser(email="test@domain.com")
    assert user.email == "test@domain.com"


@monk
class GlobalConfigUser:
    email: Annotated[str, Email]


def test_global_config_deferred_validation() -> None:
    # Turn off deferred validation globally
    settings.deferred_validation = False

    with pytest.raises(ValidationError):
        GlobalConfigUser(email="bad-email")

    # Reset config so it doesn't bleed into other tests!
    settings.deferred_validation = True


def test_env_var_global_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the environment variable correctly toggles the configuration."""
    monkeypatch.setenv("MONK_DEFERRED_VALIDATION", "false")

    import monk.config

    importlib.reload(monk.config)  # Reload the file so the top-level 'if' statement runs again
    assert monk.config.settings.deferred_validation is False

    # Clean up and restore state
    monkeypatch.delenv("MONK_DEFERRED_VALIDATION")
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
        def validate(self, field: str, value: Any) -> None:
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

        def validate(self, field: str, value: Any) -> None:
            pass

    # Ensure the decorator intercepts the missing arguments during class creation
    with pytest.raises(TypeError):

        @monk
        class FaultyAgent:
            password: Annotated[str, StatefulConstraint]
