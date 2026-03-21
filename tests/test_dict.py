import pytest
from typing import TypedDict, Annotated
from monk import monk, validate_dict
from monk.exceptions import ValidationError
from monk.constraints import Email, Interval, Nullable, Nested, Each, Len


def test_typeddict_validation() -> None:
    class UserDict(TypedDict):
        email: Annotated[str, Email]
        age: Annotated[int, Interval(ge=18)]
        nickname: Annotated[str | None, Nullable, Interval(ge=1)]

    # 1. Success (Returns the dict unchanged)
    data = {"email": "test@domain.com", "age": 25, "nickname": None}
    assert validate_dict(data, UserDict) == data

    # 2. Missing required field behaves exactly like None and raises NotNull
    with pytest.raises(ValidationError) as exc:
        validate_dict({"email": "test@domain.com"}, UserDict)
    assert exc.value.errors[0]["field"] == "age"
    assert exc.value.errors[0]["code"] == "NotNull"

    # 3. Invalid data
    with pytest.raises(ValidationError) as exc:
        validate_dict({"email": "bad", "age": 12}, UserDict)
    assert len(exc.value.errors) == 2
    assert exc.value.errors[0]["code"] == "Email"
    assert exc.value.errors[1]["code"] == "Interval"


def test_partial_validation_with_dataclass() -> None:
    @monk
    class PatchUser:
        email: Annotated[str, Email]
        age: Annotated[int, Interval(ge=18)]

    # 1. Standard POST payload (Full)
    assert validate_dict({"email": "a@b.com", "age": 20}, PatchUser) == {"email": "a@b.com", "age": 20}

    # 2. Standard Failure (Missing required)
    with pytest.raises(ValidationError) as exc:
        validate_dict({"age": 20}, PatchUser)
    assert exc.value.errors[0]["code"] == "NotNull"

    # 3. Partial Success (Ignores missing email)
    assert validate_dict({"age": 20}, PatchUser, partial=True) == {"age": 20}

    # 4. Partial Failure (Bad value still caught)
    with pytest.raises(ValidationError) as exc:
        validate_dict({"age": 12}, PatchUser, partial=True)
    assert exc.value.errors[0]["code"] == "Interval"

    # 5. Explicit None on a required field is STILL caught as NotNull
    with pytest.raises(ValidationError) as exc:
        validate_dict({"email": None}, PatchUser, partial=True)
    assert exc.value.errors[0]["code"] == "NotNull"


def test_nested_dict_validation() -> None:
    class AddressDict(TypedDict):
        city: Annotated[str, Len(min_len=2)]

    class DeepUserDict(TypedDict):
        email: Annotated[str, Email]
        address: Annotated[AddressDict, Nested(AddressDict)]
        history: Annotated[list[AddressDict], Each(Nested(AddressDict))]

    # 1. Success
    valid = {
        "email": "test@domain.com",
        "address": {"city": "New York"},
        "history": [{"city": "Los Angeles"}, {"city": "Chicago"}],
    }
    assert validate_dict(valid, DeepUserDict) == valid

    # 2. Deep Failure Path formatting
    invalid = {"email": "bad", "address": {"city": "N"}, "history": [{"city": "L"}, {"city": "C"}]}

    with pytest.raises(ValidationError) as exc:
        validate_dict(invalid, DeepUserDict)

    errors = exc.value.errors
    assert errors[0]["field"] == "email"
    assert errors[1]["field"] == "address.city"
    assert errors[2]["field"] == "history[0].city"
    assert errors[3]["field"] == "history[1].city"

    # 3. Passing a non-dictionary to a Nested constraint
    invalid_type = {"email": "test@domain.com", "address": 123, "history": []}
    with pytest.raises(ValidationError) as exc:
        validate_dict(invalid_type, DeepUserDict)

    assert exc.value.errors[0]["field"] == "address"
    assert "is not a dictionary" in exc.value.errors[0]["message"]
