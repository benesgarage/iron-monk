import pytest
from monk.constraints import (
    Slug,
    SemVer,
    Base64,
    JSON,
    HexColor,
    LatLong,
    Port,
    MacAddress,
    Interval,
    IsISO8601,
    CSV,
    LowerCase,
    Len,
)
from monk.exceptions import ValidationError


def test_slug_constraint() -> None:
    constraint = Slug()

    # Success
    constraint.validate("my-blog-post")
    constraint.validate("simple")
    constraint.validate("a-1-b")

    # Failure
    with pytest.raises(ValueError):
        constraint.validate("My-Blog-Post")  # No uppercase
    with pytest.raises(ValueError):
        constraint.validate("blog--post")  # No double hyphens
    with pytest.raises(ValueError):
        constraint.validate("-blog")  # No leading hyphens

    with pytest.raises(TypeError):
        constraint.validate(123)


def test_semver_constraint() -> None:
    constraint = SemVer()

    constraint.validate("1.0.0")
    constraint.validate("2.10.4-beta.1+build.123")

    with pytest.raises(ValueError):
        constraint.validate("1.0")
    with pytest.raises(TypeError):
        constraint.validate(123)


def test_base64_constraint() -> None:
    constraint = Base64()

    constraint.validate("SGVsbG8gV29ybGQ=")  # "Hello World"
    constraint.validate("YQ==")  # "a"

    with pytest.raises(ValueError):
        constraint.validate("SGVsbG8gV29ybGQ")  # Missing padding
    with pytest.raises(TypeError):
        constraint.validate(123)


def test_json_constraint() -> None:
    constraint = JSON()

    constraint.validate('{"key": "value", "arr": [1, 2, 3]}')

    with pytest.raises(ValueError):
        constraint.validate("{key: value}")  # Invalid JSON format
    with pytest.raises(TypeError):
        constraint.validate({"key": "value"})  # Must be a string


def test_hexcolor_constraint() -> None:
    constraint = HexColor()

    constraint.validate("#FFF")
    constraint.validate("#ff5733")
    constraint.validate("#ffffffff")

    with pytest.raises(ValueError):
        constraint.validate("FFF")  # Missing hash
    with pytest.raises(ValueError):
        constraint.validate("#12345")  # Invalid length

    with pytest.raises(TypeError):
        constraint.validate(123)


def test_latlong_constraint() -> None:
    constraint = LatLong()

    constraint.validate((45.5, -120.0))
    constraint.validate([90, 180])

    with pytest.raises(ValueError, match="Latitude"):
        constraint.validate((91.0, 0))
    with pytest.raises(ValueError, match="Longitude"):
        constraint.validate((0, 181.0))
    with pytest.raises(ValueError, match="exactly two"):
        constraint.validate((1,))

    with pytest.raises(TypeError):
        constraint.validate("45.5, -120.0")
    with pytest.raises(TypeError, match="numbers"):
        constraint.validate(("45", "-120"))
    with pytest.raises(TypeError, match="numbers"):
        constraint.validate((True, False))
    with pytest.raises(TypeError, match="numbers"):
        constraint.validate((45.0, "-120"))
    with pytest.raises(TypeError, match="numbers"):
        constraint.validate((45.0, True))


def test_port_constraint() -> None:
    constraint = Port()

    constraint.validate(80)
    constraint.validate(65535)

    with pytest.raises(ValueError):
        constraint.validate(0)
    with pytest.raises(ValueError):
        constraint.validate(65536)

    with pytest.raises(TypeError):
        constraint.validate("80")
    with pytest.raises(TypeError):
        constraint.validate(True)


def test_macaddress_constraint() -> None:
    constraint = MacAddress()

    constraint.validate("00:1A:2B:3C:4D:5E")
    constraint.validate("00-1A-2B-3C-4D-5E")

    with pytest.raises(ValueError):
        constraint.validate("00:1A:2B:3C:4D")  # Too short
    with pytest.raises(ValueError):
        constraint.validate("00:1A:2B:3C:4D:5Z")  # Z is not valid hex

    with pytest.raises(TypeError):
        constraint.validate(123)

    with pytest.raises(TypeError):
        constraint.validate(123)


def test_is_iso8601_constraint() -> None:
    constraint = IsISO8601()

    # Success
    constraint.validate("2024-01-01")
    constraint.validate("2024-01-01T15:30:00")
    constraint.validate("2024-01-01T15:30:00Z")
    constraint.validate("2024-01-01T15:30:00+02:00")

    # Failure
    with pytest.raises(ValueError):
        constraint.validate("2024/01/01")
    with pytest.raises(ValueError):
        constraint.validate("not a date")

    # Type Error (must be a string, not an already parsed datetime!)
    import datetime

    with pytest.raises(TypeError):
        constraint.validate(datetime.datetime.now())


def test_csv_constraint() -> None:
    constraint = CSV(LowerCase, Len(min_len=2), separator=",")

    constraint.validate("abc,def,ghi")
    constraint.validate("ab")
    constraint.validate("")  # Empty string passes gracefully

    # Failure (Aggregates multiple errors across the string)
    with pytest.raises(ValidationError) as exc:
        constraint.validate("abc,d,GHI")

    errors = exc.value.errors
    assert len(errors) == 2
    # 'd' fails Len
    assert errors[0]["field"] == "[1]"
    assert errors[0]["code"] == "Len"
    # 'GHI' fails LowerCase
    assert errors[1]["field"] == "[2]"
    assert errors[1]["code"] == "Predicate"  # LowerCase is a Predicate

    # Type Error
    with pytest.raises(TypeError):
        constraint.validate(123)

    # Incompatible constraint
    constraint = CSV(Interval(ge=2), separator=",")
    with pytest.raises(ValidationError) as exc2:
        constraint.validate("123,456")
    assert exc2.value.errors[0]["code"] == "Interval"

    # Nested CSV to trigger the ValidationError aggregation block
    nested_csv = CSV(CSV(Len(min_len=3), separator="|"), separator=",")
    with pytest.raises(ValidationError) as exc_nested:
        nested_csv.validate("ab|cde,fgh|i")

    nested_errors = exc_nested.value.errors
    assert len(nested_errors) == 2
    assert nested_errors[0]["field"] == "[0][0]"  # 'ab' fails Len (index 0 outer, index 0 inner)
    assert nested_errors[1]["field"] == "[1][1]"  # 'i' fails Len (index 1 outer, index 1 inner)


def test_csv_constraint_unique() -> None:
    from monk.constraints import CSV

    constraint = CSV(separator=",", unique=True)

    constraint.validate("apple,banana,orange")

    with pytest.raises(ValidationError) as exc:
        constraint.validate("apple,banana,apple")

    assert exc.value.errors[0]["field"] == "[2]"
    assert exc.value.errors[0]["code"] == "Unique"
    assert "unique" in exc.value.errors[0]["message"]
