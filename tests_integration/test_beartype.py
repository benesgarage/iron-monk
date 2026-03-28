import pytest
from typing import Annotated
from monk import monk, validate
from monk.constraints import Email, Interval
from monk.exceptions import ValidationError


def test_beartype_integration() -> None:
    from beartype import beartype
    from beartype.roar import BeartypeCallHintParamViolation

    @beartype
    @monk
    class BeartypeUser:
        email: Annotated[str, Email]
        age: Annotated[int, Interval(ge=18)]

    with pytest.raises(BeartypeCallHintParamViolation):
        BeartypeUser(email="test@domain.com", age="twenty")  # type: ignore

    with pytest.raises(ValidationError) as exc:
        validate(BeartypeUser(email="bad-email", age=12))

    assert len(exc.value.errors) == 2
