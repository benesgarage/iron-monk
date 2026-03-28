import pytest
from typing import Annotated
from monk import monk, validate
from monk.constraints import Email, Len
from monk.exceptions import ValidationError


def test_tortoise_orm_integration() -> None:
    import dataclasses
    from tortoise.models import Model
    from tortoise import fields

    class UserDB(Model):
        id = fields.IntField(primary_key=True)
        username = fields.CharField(max_length=50, unique=True)
        email = fields.CharField(max_length=255, unique=True)

        class Meta:
            table = "users"

    @monk
    class CreateUserDTO:
        username: Annotated[str, Len(min_len=3, max_len=50)]
        email: Annotated[str, Email]

    with pytest.raises(ValidationError):
        validate(CreateUserDTO(username="ab", email="bad-email"))

    dto = validate(CreateUserDTO(username="kai", email="test@domain.com"))
    user = UserDB(**dataclasses.asdict(dto))

    assert user.username == "kai"
    assert user.email == "test@domain.com"
