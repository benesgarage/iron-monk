import pytest
from monk import validate_value
from monk.constraints import Email, Interval, Len, Nullable
from monk.exceptions import ValidationError


def test_passes_single_constraint() -> None:
    validate_value("hello@example.com", Email)
    validate_value("hello@example.com", Email())


def test_passes_multiple_constraints() -> None:
    validate_value("hello", Len(min_len=3), Len(max_len=10))


def test_raises_single_failure() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_value("not-an-email", Email)
    assert len(exc.value.errors) == 1
    assert exc.value.errors[0]["field"] == "value"
    assert exc.value.errors[0]["code"] == "Email"


def test_aggregates_multiple_failures() -> None:
    """All constraint failures collected; not fail-fast."""
    with pytest.raises(ValidationError) as exc:
        validate_value("X", Len(min_len=3), Email)
    codes = [e["code"] for e in exc.value.errors]
    assert codes == ["Len", "Email"]
    assert all(e["field"] == "value" for e in exc.value.errors)


def test_custom_field_name() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_value(5, Interval(ge=18), field_name="age")
    assert exc.value.errors[0]["field"] == "age"
    assert exc.value.flatten() == ["age: Must be greater than or equal to 18."]


def test_default_field_name_in_flatten() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_value(-1, Interval(ge=0))
    assert exc.value.flatten() == ["value: Must be greater than or equal to 0."]


def test_bare_class_auto_instantiates() -> None:
    validate_value("hello@example.com", Email)  # bare class auto-calls Email()
    with pytest.raises(ValidationError):
        validate_value("nope", Email)


def test_missing_constraint_raises_type_error() -> None:
    """Signature requires at least one constraint."""
    with pytest.raises(TypeError):
        validate_value("anything")  # type: ignore[call-arg]


def test_none_rejected_without_nullable() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_value(None, Email)
    assert exc.value.errors[0]["code"] == "NotNull"


def test_none_allowed_with_nullable() -> None:
    validate_value(None, Nullable, Email)


def test_constraint_missing_args_raises_type_error() -> None:
    """Bare class that requires args reports a helpful error."""
    from monk.constraints import Match

    with pytest.raises(TypeError, match="missing required arguments"):
        validate_value("abc", Match)
