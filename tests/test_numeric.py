import pytest
from monk.constraints import (
    Interval,
    MultipleOf,
    IsFinite,
    IsNan,
    IsInfinite,
    NonNegative,
    Positive,
    Negative,
    NonZero,
    Even,
    Odd,
    PowerOfTwo,
)


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

    # Type Errors
    with pytest.raises(TypeError):
        constraint.validate("string")


def test_multiple_of_constraint() -> None:
    constraint = MultipleOf(5)

    constraint.validate(10)

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


def test_positive_singleton() -> None:
    Positive.validate(1)
    Positive.validate(0.0001)
    with pytest.raises(ValueError):
        Positive.validate(0)
    with pytest.raises(ValueError):
        Positive.validate(-1)


def test_negative_singleton() -> None:
    Negative.validate(-1)
    Negative.validate(-0.0001)
    with pytest.raises(ValueError):
        Negative.validate(0)
    with pytest.raises(ValueError):
        Negative.validate(1)


def test_nonzero_constraint() -> None:
    constraint = NonZero()
    constraint.validate(1)
    constraint.validate(-1)
    constraint.validate(0.5)
    with pytest.raises(ValueError):
        constraint.validate(0)
    with pytest.raises(ValueError):
        constraint.validate(0.0)

    # Type that raises on equality comparison
    class _BadEq:
        def __eq__(self, other: object) -> bool:
            raise TypeError("incompatible")

        def __hash__(self) -> int:
            return 0

    with pytest.raises(TypeError):
        constraint.validate(_BadEq())


def test_even_constraint() -> None:
    constraint = Even()
    constraint.validate(0)
    constraint.validate(2)
    constraint.validate(-4)
    with pytest.raises(ValueError):
        constraint.validate(1)
    with pytest.raises(ValueError):
        constraint.validate(-3)
    with pytest.raises(TypeError):
        constraint.validate(2.0)
    with pytest.raises(TypeError):
        constraint.validate(True)


def test_odd_constraint() -> None:
    constraint = Odd()
    constraint.validate(1)
    constraint.validate(-3)
    with pytest.raises(ValueError):
        constraint.validate(0)
    with pytest.raises(ValueError):
        constraint.validate(2)
    with pytest.raises(TypeError):
        constraint.validate(1.0)
    with pytest.raises(TypeError):
        constraint.validate(False)


def test_power_of_two_constraint() -> None:
    constraint = PowerOfTwo()
    for v in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024):
        constraint.validate(v)
    with pytest.raises(ValueError):
        constraint.validate(0)
    with pytest.raises(ValueError):
        constraint.validate(-2)
    with pytest.raises(ValueError):
        constraint.validate(3)
    with pytest.raises(ValueError):
        constraint.validate(6)
    with pytest.raises(TypeError):
        constraint.validate(2.0)
    with pytest.raises(TypeError):
        constraint.validate(True)
