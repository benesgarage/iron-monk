import pytest
from typing import TypedDict, Annotated
from monk import validate_dict
from monk.exceptions import ValidationError
from monk.constraints import Email, Interval, Nullable


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
