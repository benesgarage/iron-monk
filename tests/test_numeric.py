import pytest
from monk.constraints import Interval, MultipleOf, IsFinite, IsNan, IsInfinite, NonNegative


def test_interval_constraint():
    # Exclusive bounds
    constraint = Interval(gt=5, lt=10)
    constraint.validate("val", 6)
    with pytest.raises(ValueError): constraint.validate("val", 5)
    with pytest.raises(ValueError): constraint.validate("val", 10)
    
    # Inclusive bounds
    constraint_inclusive = Interval(ge=5, le=10)
    constraint_inclusive.validate("val", 5)
    constraint_inclusive.validate("val", 10)
    with pytest.raises(ValueError): constraint_inclusive.validate("val", 4)
    with pytest.raises(ValueError): constraint_inclusive.validate("val", 11)
    
    # Nullability & Type Errors
    constraint.validate("val", None)
    with pytest.raises(TypeError): constraint.validate("val", "string")


def test_multiple_of_constraint():
    constraint = MultipleOf(5)
    
    constraint.validate("val", 10)
    constraint.validate("val", None)
    
    with pytest.raises(ValueError): constraint.validate("val", 11)
    with pytest.raises(TypeError): constraint.validate("val", "string")
    with pytest.raises(ValueError, match="cannot be 0"): MultipleOf(0)


def test_numeric_predicates():
    IsFinite.validate("val", 5)
    with pytest.raises(ValueError): IsFinite.validate("val", float("inf"))
    
    IsNan.validate("val", float("nan"))
    with pytest.raises(ValueError): IsNan.validate("val", 5)
    
    IsInfinite.validate("val", float("inf"))
    with pytest.raises(ValueError): IsInfinite.validate("val", 5)


def test_non_negative_singleton():
    NonNegative.validate("val", 0)
    NonNegative.validate("val", 5)
    with pytest.raises(ValueError): NonNegative.validate("val", -1)