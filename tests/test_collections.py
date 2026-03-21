import pytest
from dataclasses import field
from typing import Annotated, Iterator

from monk import monk, validate
from monk.exceptions import ValidationError
from monk.constraints import Each, Len, LowerCase, Email, Unique, Contains, OneOf, MultipleOf, Nullable, NotNull


# --- Raw Constraint Tests ---


def test_len_constraint_success() -> None:
    constraint = Len(min_len=2, max_len=4)

    # Should work on lists, strings, and dictionaries
    constraint.validate([1, 2])
    constraint.validate([1, 2, 3, 4])
    constraint.validate("abc")
    constraint.validate({"a": 1, "b": 2})


def test_len_constraint_failure() -> None:
    constraint = Len(min_len=2, max_len=4)

    with pytest.raises(ValueError):
        constraint.validate([1])

    with pytest.raises(ValueError):
        constraint.validate([1, 2, 3, 4, 5])


def test_len_init_failure() -> None:
    with pytest.raises(ValueError):
        Len(min_len=5, max_len=2)


def test_len_type_error() -> None:
    constraint = Len(min_len=1)
    with pytest.raises(TypeError):
        constraint.validate(123)  # Integers have no length


def test_contains_constraint_success() -> None:
    constraint = Contains("apple")

    # Lists
    constraint.validate(["apple", "banana"])
    # Strings (substrings)
    constraint.validate("I ate an apple pie")
    # Dicts (checks keys)
    constraint.validate({"apple": 1, "orange": 2})


def test_contains_constraint_failure() -> None:
    constraint = Contains("apple")

    with pytest.raises(ValueError):
        constraint.validate(["banana", "orange"])


def test_contains_type_error() -> None:
    constraint = Contains("apple")
    with pytest.raises(TypeError):
        constraint.validate(123)


def test_unique_constraint_success() -> None:
    Unique().validate([1, 2, 3, 4])
    Unique().validate(("a", "b", "c"))
    Unique().validate({1, 2, 3})

    # Deeply nested unhashable structures
    Unique().validate([[1, 2], [3, 4]])
    Unique().validate([[{"a": [1]}, {"b": [2]}], [{"c": [3]}]])


def test_unique_constraint_failure() -> None:
    with pytest.raises(ValueError):
        Unique().validate([1, 2, 2, 3])
    with pytest.raises(ValueError):
        Unique().validate([[1, 2], [1, 2]])
    with pytest.raises(ValueError):
        Unique().validate([[{"a": [1]}], [{"a": [1]}]])
    with pytest.raises(ValueError):
        Unique().validate([[1, [2, 3]], [1, [2, 3]]])


def test_unique_type_error() -> None:
    with pytest.raises(TypeError):
        Unique().validate(123)


def test_unique_non_sized_iterable() -> None:
    """Tests that a re-usable Iterable without __len__ is safely converted to a tuple."""

    class ReusableIterable:
        def __init__(self, data: list[int]):
            self.data = data

        def __iter__(self) -> Iterator[int]:
            for item in self.data:
                yield item

    # Not an Iterator, not Sized, but IS an Iterable!
    Unique().validate(ReusableIterable([1, 2, 3]))

    with pytest.raises(ValueError):
        Unique().validate(ReusableIterable([1, 1]))


def test_exhaustible_iterator_rejection() -> None:
    """Ensure constraints that iterate over values refuse to silently consume generators."""
    gen = (x for x in [1, 2, 3])

    with pytest.raises(TypeError, match="Cannot eagerly validate exhaustible iterator"):
        Each(LowerCase).validate(gen)
    with pytest.raises(TypeError, match="Cannot eagerly validate exhaustible iterator"):
        Contains(2).validate(gen)
    with pytest.raises(TypeError, match="Cannot eagerly validate exhaustible iterator"):
        Unique().validate(gen)


def test_one_of_constraint_success() -> None:
    constraint = OneOf(["active", "pending", "closed"])

    constraint.validate("active")
    constraint.validate("closed")


def test_one_of_constraint_failure() -> None:
    constraint = OneOf(["active", "pending", "closed"])

    with pytest.raises(ValueError):
        constraint.validate("archived")


def test_one_of_init_failure() -> None:
    # Developer experience check: ensuring they don't create empty constraints
    with pytest.raises(ValueError):
        OneOf([])


def test_one_of_generator_conversion() -> None:
    # Prove that passing an exhaustible generator safely converts to a tuple internally
    constraint = OneOf(x for x in ["a", "b"])
    constraint.validate("a")


def test_each_init_and_type_failure() -> None:
    with pytest.raises(ValueError):
        Each()

    with pytest.raises(TypeError):
        Each(LowerCase).validate(123)

    with pytest.raises(TypeError, match="missing required arguments"):
        Each(MultipleOf)


def test_each_nullability_failure() -> None:
    # Prove that the Each constraint does NOT skip None items, and properly raises NotNull errors
    with pytest.raises(ValidationError) as exc:
        Each(LowerCase).validate(["hello", None, "world"])

    errors = exc.value.errors
    assert len(errors) == 1
    assert errors[0]["field"] == "[1]"
    assert errors[0]["code"] == "NotNull"
    assert "cannot be null" in errors[0]["message"]


def test_nullable_marker() -> None:
    # 0. Cover the dummy validate method required by the MonkConstraint Protocol
    Nullable().validate("anything")
    NotNull().validate("anything")

    # 1. Success & Nullability
    constraint = Each(Nullable, LowerCase)
    constraint.validate(["hello", None])

    # 2. Failure
    with pytest.raises(ValidationError) as exc:
        constraint.validate(["HELLO", None])
    assert "islower" in exc.value.errors[0]["message"]

    # 3. Requires other constraints
    with pytest.raises(ValueError, match="functional constraint besides markers"):
        Each(Nullable)

    # 4. NotNull inside Each
    constraint_not_null = Each(NotNull, LowerCase)
    with pytest.raises(ValidationError) as exc_nn:
        constraint_not_null.validate(["hello", None])
    assert exc_nn.value.errors[0]["field"] == "[1]"
    assert exc_nn.value.errors[0]["code"] == "NotNull"


# --- Dataclass Integration Tests ---


@monk
class Team:
    # Multiple constraints on each element
    members: Annotated[list[str], Each(Len(min_len=3), LowerCase)]
    # Combining collection-level constraints (Unique) with item-level constraints (Each)
    contact_emails: Annotated[list[str], Unique, Each(Email)]
    # 2D Nested Array check
    matrix: Annotated[list[list[str]], Each(Each(LowerCase))]
    # Collection-level constraints
    department: Annotated[str, OneOf(["engineering", "sales", "marketing"])]
    tags: Annotated[list[str], Contains("core")]
    # Ensure we skip validation if None is present
    managers: Annotated[list[str] | None, Nullable, Each(Len(max_len=50))] = None
    # Ensure we gracefully handle explicit nested nulls
    sparse_matrix: Annotated[list[list[str | None]], Each(Each(Nullable, LowerCase))] = field(default_factory=list)


def test_each_constraint_success() -> None:
    team = Team(
        members=["alice", "bob", "charlie"],
        contact_emails=["a@b.com", "test@domain.com"],
        matrix=[["a", "b"], ["c", "d"]],
        department="engineering",
        tags=["backend", "core"],
        sparse_matrix=[["a", None], [None, "b"]],
    )
    validate(team)  # Should not raise


def test_each_constraint_failure() -> None:
    team = Team(
        members=["al", "Bob", "charlie"],
        contact_emails=["a@b.com", "not-email"],
        matrix=[["a", "B"]],
        department="engineeri",
        tags=["backend"],
        sparse_matrix=[["A", None]],
    )

    with pytest.raises(ValidationError) as exc:
        validate(team)

    errors = exc.value.errors
    assert len(errors) == 7

    assert "members" in errors[0]["field"]  # 'al' failed length
    assert "members" in errors[1]["field"]  # 'Bob' failed LowerCase
    assert "contact_emails" in errors[2]["field"]  # 'not-email' failed Email
    assert "matrix" in errors[3]["field"]  # 'B' failed LowerCase in the nested array
    assert "department" in errors[4]["field"]  # 'engineeri' fails OneOf
    assert "tags" in errors[5]["field"]  # Does not contain 'core'
    assert "sparse_matrix[0][0]" in errors[6]["field"]  # 'A' failed LowerCase
