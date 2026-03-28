import pytest
from typing import Annotated
from monk import monk, validate
from monk.constraints import Len
from monk.exceptions import ValidationError


def test_sqlalchemy_dto_integration() -> None:
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

    class Base(DeclarativeBase):
        pass

    class UserDB(Base):
        __tablename__ = "users"
        id: Mapped[int] = mapped_column(primary_key=True)
        username: Mapped[str]

    @monk
    class CreateUserDTO:
        username: Annotated[str, Len(min_len=3)]

    with pytest.raises(ValidationError):
        validate(CreateUserDTO(username="ab"))

    dto = validate(CreateUserDTO(username="kai"))
    user = UserDB(username=dto.username)
    assert user.username == "kai"
