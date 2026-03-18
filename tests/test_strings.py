import pytest
import pathlib
from typing import Annotated, Any
from monk import monk, validate
from monk.exceptions import ValidationError, UnvalidatedAccessError
from monk.constraints import (
    Email,
    Not,
    Match,
    StartsWith,
    EndsWith,
    LowerCase,
    UpperCase,
    IsDigit,
    IsAscii,
    IsDir,
    IsFile,
)


@pytest.mark.parametrize(
    "valid_email",
    [
        "test@example.com",
        "first.last@example.com",
        "user+tag@example.com",
        "user_name@example.com",
        "user-name@example.com",
        "1234567890@example.com",
        "a@b.c",
        "TEST@EXAMPLE.COM",
        "test@sub.domain.co.uk",
        "test@my-domain.com",
        "test@domain.technology",
        "t@123.com",
        "first..last@example.com",
        "+@example.com",
        "_______@example.com",
        "a.b.c.d.e@example.com",
        "test@123.123.123.123",
        "1@1.1",
    ],
)
def test_email_success(valid_email: str) -> None:
    # Should execute silently without raising any errors
    Email().validate("email", valid_email)


@pytest.mark.parametrize(
    "invalid_email",
    [
        "plainaddress",
        "@no-local-part.com",
        "no-at.com",
        "no-tld@domain",
        "spaces in@email.com",
        "test@domain..com",
        "",
        "test@domain_name.com",
        '"john.doe"@example.com',
        " test@example.com",
        "test@example.com ",
        "email@domain@domain.com",
        "test@.com",
        "test@example.com\n",
        "user@ñ.com",
    ],
)
def test_email_failure(invalid_email: str) -> None:
    with pytest.raises(ValueError):
        Email().validate("email", invalid_email)


def test_email_nullability() -> None:
    # Should return silently without validation errors
    Email().validate("email", None)


@pytest.mark.parametrize(
    "invalid_type",
    [
        123,
        ["test@example.com"],
        {"email": "test@example.com"},
    ],
)
def test_email_type_error(invalid_type: Any) -> None:
    with pytest.raises(TypeError):
        Email().validate("email", invalid_type)


# --- Raw String Constraints ---


def test_match_constraint() -> None:
    constraint = Match(r"^PROD-\d+$")

    # Success & Nullability
    constraint.validate("sku", "PROD-12345")
    constraint.validate("sku", None)

    # Failure
    with pytest.raises(ValueError):
        constraint.validate("sku", "DEV-12345")

    # Type Error
    with pytest.raises(TypeError):
        constraint.validate("sku", 12345)


def test_startswith_constraint() -> None:
    constraint = StartsWith("admin_")

    # Success & Nullability
    constraint.validate("role", "admin_user")
    constraint.validate("role", None)

    # Failure
    with pytest.raises(ValueError):
        constraint.validate("role", "user_admin")

    # Type Error
    with pytest.raises(TypeError):
        constraint.validate("role", 123)


def test_endswith_constraint() -> None:
    constraint = EndsWith(".csv")

    # Success & Nullability
    constraint.validate("filename", "data.csv")
    constraint.validate("filename", None)

    # Failure
    with pytest.raises(ValueError):
        constraint.validate("filename", "data.json")

    # Type Error
    with pytest.raises(TypeError):
        constraint.validate("filename", 123)


def test_string_predicates() -> None:
    # LowerCase
    LowerCase.validate("word", "hello")
    with pytest.raises(ValueError):
        LowerCase.validate("word", "Hello")

    # UpperCase
    UpperCase.validate("word", "HELLO")
    with pytest.raises(ValueError):
        UpperCase.validate("word", "Hello")

    # IsDigit
    IsDigit.validate("num", "123")
    with pytest.raises(ValueError):
        IsDigit.validate("num", "123a")

    # IsAscii
    IsAscii.validate("text", "hello")
    with pytest.raises(ValueError):
        IsAscii.validate("text", "helloñ")

    # Type Error catching for predicates
    with pytest.raises(TypeError):
        LowerCase.validate("word", 123)


# --- Path Constraints ---


def test_path_constraints(tmp_path: pathlib.Path) -> None:
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello")

    IsDir().validate("dir", tmp_path)
    IsDir().validate("dir", str(tmp_path))
    IsDir().validate("dir", None)
    with pytest.raises(ValueError):
        IsDir().validate("dir", file_path)
    with pytest.raises(TypeError):
        IsDir().validate("dir", 123)

    IsFile().validate("file", file_path)
    IsFile().validate("file", str(file_path))
    IsFile().validate("file", None)
    with pytest.raises(ValueError):
        IsFile().validate("file", tmp_path)
    with pytest.raises(TypeError):
        IsFile().validate("file", 123)


# --- Dataclass Integration Tests ---


@monk
class UserProfile:
    primary_email: Annotated[str, Email]
    not_an_email: Annotated[str, Not(Email)]
    sku: Annotated[str, Match(r"^PROD-\d+$")]
    role: Annotated[str, StartsWith("admin_")]
    avatar_file: Annotated[str, EndsWith(".png")]
    username: Annotated[str, LowerCase]
    department_code: Annotated[str, UpperCase]
    pin_code: Annotated[str, IsDigit]
    bio: Annotated[str, IsAscii]


def test_string_dataclass_lifecycle_success() -> None:
    profile = UserProfile(
        primary_email="valid@example.com",
        not_an_email="just_a_string",
        sku="PROD-12345",
        role="admin_superuser",
        avatar_file="profile.png",
        username="johndoe",
        department_code="SALES",
        pin_code="1234",
        bio="Hello world!",
    )

    with pytest.raises(UnvalidatedAccessError):
        _ = profile.primary_email

    validated_profile = validate(profile)

    assert validated_profile.primary_email == "valid@example.com"
    assert validated_profile.not_an_email == "just_a_string"
    assert validated_profile.sku == "PROD-12345"
    assert validated_profile.username == "johndoe"


def test_string_dataclass_lifecycle_failure() -> None:
    profile = UserProfile(
        primary_email="just_a_string",
        not_an_email="valid@example.com",
        sku="DEV-12345",
        role="user_admin",
        avatar_file="profile.jpg",
        username="JohnDoe",
        department_code="sales",
        pin_code="1234a",
        bio="Hello ñ",
    )
    with pytest.raises(ValidationError) as exc_info:
        validate(profile)

    # Assert that we received a structured list of all errors
    errors = exc_info.value.errors
    assert len(errors) == 9
