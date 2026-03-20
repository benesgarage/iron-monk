import pytest
from monk.constraints import Interval, MultipleOf, IsFinite, IsNan, IsInfinite, NonNegative


def test_interval_constraint() -> None:
    # Exclusive bounds
    constraint = Interval(gt=5, lt=10)
    constraint.validate(6)
    with pytest.raises(ValueError):
        constraint.validate(5)
    with pytest.raises(ValueError):
        constraint.validate(10)

    # Inclusive bounds
    constraint_inclusive = Interval(ge=5, le=10)
    constraint_inclusive.validate(5)
    constraint_inclusive.validate(10)
    with pytest.raises(ValueError):
        constraint_inclusive.validate(4)
    with pytest.raises(ValueError):
        constraint_inclusive.validate(11)

    # Nullability & Type Errors
    constraint.validate(None)
    with pytest.raises(TypeError):
        constraint.validate("string")


def test_multiple_of_constraint() -> None:
    constraint = MultipleOf(5)

    constraint.validate(10)
    constraint.validate(None)

    with pytest.raises(ValueError):
        constraint.validate(11)
    with pytest.raises(TypeError):
        constraint.validate("string")
    with pytest.raises(ValueError, match="cannot be 0"):
        MultipleOf(0)


def test_numeric_predicates() -> None:
    IsFinite.validate(5)
    with pytest.raises(ValueError):
        IsFinite.validate(float("inf"))

    IsNan.validate(float("nan"))
    with pytest.raises(ValueError):
        IsNan.validate(5)

    IsInfinite.validate(float("inf"))
    with pytest.raises(ValueError):
        IsInfinite.validate(5)


def test_non_negative_singleton() -> None:
    NonNegative.validate(0)
    NonNegative.validate(5)
    with pytest.raises(ValueError):
        NonNegative.validate(-1)
