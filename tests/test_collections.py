import pytest
from typing import Annotated
from monk import monk, validate
from monk.exceptions import ValidationError
from monk.constraints import Each, Len, LowerCase, Email, Unique, Contains, OneOf, MultipleOf


# --- Raw Constraint Tests ---


def test_len_constraint_success() -> None:
    constraint = Len(min_len=2, max_len=4)

    # Should work on lists, strings, and dictionaries
    constraint.validate("items", [1, 2])
    constraint.validate("items", [1, 2, 3, 4])
    constraint.validate("word", "abc")
    constraint.validate("mapping", {"a": 1, "b": 2})

    # Nullability
    constraint.validate("items", None)


def test_len_constraint_failure() -> None:
    constraint = Len(min_len=2, max_len=4)

    with pytest.raises(ValueError):
        constraint.validate("items", [1])

    with pytest.raises(ValueError):
        constraint.validate("items", [1, 2, 3, 4, 5])


def test_len_init_failure() -> None:
    with pytest.raises(ValueError):
        Len(min_len=5, max_len=2)


def test_len_type_error() -> None:
    constraint = Len(min_len=1)
    with pytest.raises(TypeError):
        constraint.validate("number", 123)  # Integers have no length


def test_contains_constraint_success() -> None:
    constraint = Contains("apple")

    # Lists
    constraint.validate("basket", ["apple", "banana"])
    # Strings (substrings)
    constraint.validate("phrase", "I ate an apple pie")
    # Dicts (checks keys)
    constraint.validate("mapping", {"apple": 1, "orange": 2})

    constraint.validate("basket", None)


def test_contains_constraint_failure() -> None:
    constraint = Contains("apple")

    with pytest.raises(ValueError):
        constraint.validate("basket", ["banana", "orange"])


def test_contains_type_error() -> None:
    constraint = Contains("apple")
    with pytest.raises(TypeError):
        constraint.validate("number", 123)


def test_unique_constraint_success() -> None:
    Unique().validate("items", [1, 2, 3, 4])
    Unique().validate("items", ("a", "b", "c"))
    Unique().validate("items", {1, 2, 3})
    Unique().validate("items", None)

    # Deeply nested unhashable structures
    Unique().validate("matrix", [[1, 2], [3, 4]])
    Unique().validate("deep", [[{"a": [1]}, {"b": [2]}], [{"c": [3]}]])


def test_unique_constraint_failure() -> None:
    with pytest.raises(ValueError):
        Unique().validate("items", [1, 2, 2, 3])
    with pytest.raises(ValueError):
        Unique().validate("matrix", [[1, 2], [1, 2]])
    with pytest.raises(ValueError):
        Unique().validate("deep", [[{"a": [1]}], [{"a": [1]}]])
    with pytest.raises(ValueError):
        Unique().validate("deep", [[1, [2, 3]], [1, [2, 3]]])


def test_unique_type_error() -> None:
    with pytest.raises(TypeError):
        Unique().validate("number", 123)


def test_unique_generator_conversion() -> None:
    # Prove that passing an exhaustible generator safely converts to a tuple internally
    Unique().validate("items", (x for x in [1, 2, 3]))
    with pytest.raises(ValueError):
        Unique().validate("items", (x for x in [1, 1]))


def test_one_of_constraint_success() -> None:
    constraint = OneOf(["active", "pending", "closed"])

    constraint.validate("status", "active")
    constraint.validate("status", "closed")
    constraint.validate("status", None)


def test_one_of_constraint_failure() -> None:
    constraint = OneOf(["active", "pending", "closed"])

    with pytest.raises(ValueError):
        constraint.validate("status", "archived")


def test_one_of_init_failure() -> None:
    # Developer experience check: ensuring they don't create empty constraints
    with pytest.raises(ValueError):
        OneOf([])


def test_one_of_generator_conversion() -> None:
    # Prove that passing an exhaustible generator safely converts to a tuple internally
    constraint = OneOf(x for x in ["a", "b"])
    constraint.validate("status", "a")


def test_each_init_and_type_failure() -> None:
    with pytest.raises(ValueError):
        Each()

    with pytest.raises(TypeError):
        Each(LowerCase).validate("field", 123)

    with pytest.raises(TypeError, match="missing required arguments"):
        Each(MultipleOf)


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
    managers: Annotated[list[str] | None, Each(Len(max_len=50))] = None


def test_each_constraint_success() -> None:
    team = Team(
        members=["alice", "bob", "charlie"],
        contact_emails=["a@b.com", "test@domain.com"],
        matrix=[["a", "b"], ["c", "d"]],
        department="engineering",
        tags=["backend", "core"],
    )
    validate(team)  # Should not raise


def test_each_constraint_failure() -> None:
    team = Team(
        members=["al", "Bob", "charlie"],
        contact_emails=["a@b.com", "not-email"],
        matrix=[["a", "B"]],
        department="engineeri",
        tags=["backend"],
    )

    with pytest.raises(ValidationError) as exc:
        validate(team)

    errors = exc.value.errors
    assert len(errors) == 6

    assert "members" in errors[0]["field"]  # 'al' failed length
    assert "members" in errors[1]["field"]  # 'Bob' failed LowerCase
    assert "contact_emails" in errors[2]["field"]  # 'not-email' failed Email
    assert "matrix" in errors[3]["field"]  # 'B' failed LowerCase in the nested array
    assert "department" in errors[4]["field"]  # 'engineeri' fails OneOf
    assert "tags" in errors[5]["field"]  # Does not contain 'core'
