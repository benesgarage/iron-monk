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
    JWT,
    IsISO8601,
    Cron,
    CSV,
    LowerCase,
    Len,
    PhoneE164,
    MimeType,
    Hash,
    CreditCard,
    ISBN,
    HexString,
    TimezoneName,
    Sorted,
    NoWhitespace,
    SingleLine,
    Printable,
    MaxBytes,
    PathSafe,
    Hostname,
    HttpURL,
    DataURI,
    TimeOfDay,
    PEMBlock,
    AllEqual,
    NonEmpty,
    IsTzAware,
    IsTzNaive,
    DecimalPlaces,
    OneOf,
    Email,
    Trimmed,
    StartsWith,
    EndsWith,
    Match,
    FileSize,
    MagicBytes,
    Ref,
    Ctx,
)
from typing import Annotated
from monk import monk, validate
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


def test_cron_constraint() -> None:
    standard = Cron()
    aws = Cron(allow_aws=True)

    # Standard Success
    standard.validate("* * * * *")
    standard.validate("0 12 * * 1-5")
    standard.validate("@daily")

    # Standard Failure
    with pytest.raises(ValueError, match="5-field"):
        standard.validate("* * * * * *")  # 6 fields
    with pytest.raises(ValueError, match="invalid cron characters"):
        standard.validate("0 12 & * *")
    with pytest.raises(ValueError, match="Invalid cron macro"):
        standard.validate("@bi-yearly")

    # AWS Success
    aws.validate("0 12 * * ? *")
    aws.validate("15 10 ? * 6L 2022-2023")

    # AWS Failure
    with pytest.raises(ValueError, match="6-field"):
        aws.validate("* * * * ?")  # 5 fields
    with pytest.raises(ValueError, match="exactly one '\\?'"):
        aws.validate("0 12 * * * *")  # Missing ?
    with pytest.raises(ValueError, match="exactly one '\\?'"):
        aws.validate("0 12 ? * ? *")  # Two ?

    with pytest.raises(TypeError):
        standard.validate(123)


def test_jwt_constraint() -> None:
    constraint = JWT()

    # Success
    constraint.validate(
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    constraint.validate("eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIxMjM0NTY3ODkwIn0.")  # Empty signature

    # Failure
    with pytest.raises(ValueError):
        constraint.validate("not-a-jwt")
    with pytest.raises(ValueError):
        constraint.validate("header.payload.sig.extra")  # Too many dots
    with pytest.raises(ValueError):
        constraint.validate("header.payload+invalid_chars")  # Invalid Base64Url chars

    with pytest.raises(TypeError):
        constraint.validate(123)


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


def test_phone_e164_constraint() -> None:
    constraint = PhoneE164()
    constraint.validate("+14155552671")
    constraint.validate("+442071838750")
    constraint.validate("+919876543210")

    with pytest.raises(ValueError):
        constraint.validate("14155552671")  # missing +
    with pytest.raises(ValueError):
        constraint.validate("+04155552671")  # leading 0 after +
    with pytest.raises(ValueError):
        constraint.validate("+1")  # too short
    with pytest.raises(ValueError):
        constraint.validate("+1234567890123456")  # too long (>15 digits)
    with pytest.raises(ValueError):
        constraint.validate("+1-415-555-2671")  # dashes not allowed
    with pytest.raises(TypeError):
        constraint.validate(14155552671)


def test_mime_type_constraint() -> None:
    constraint = MimeType()
    constraint.validate("application/json")
    constraint.validate("text/html")
    constraint.validate("text/html; charset=utf-8")
    constraint.validate("application/vnd.api+json")
    constraint.validate("multipart/form-data; boundary=xyz")
    constraint.validate('text/plain; charset="utf-8"')

    with pytest.raises(ValueError):
        constraint.validate("application")  # no slash
    with pytest.raises(ValueError):
        constraint.validate("application/")  # missing subtype
    with pytest.raises(ValueError):
        constraint.validate("/json")  # missing type
    with pytest.raises(ValueError):
        constraint.validate("text/html charset=utf-8")  # missing semicolon
    with pytest.raises(TypeError):
        constraint.validate(123)


def test_hash_constraint() -> None:
    md5 = Hash(algorithm="md5")
    md5.validate("d41d8cd98f00b204e9800998ecf8427e")
    sha1 = Hash(algorithm="sha1")
    sha1.validate("da39a3ee5e6b4b0d3255bfef95601890afd80709")
    sha256 = Hash(algorithm="SHA256")  # case-insensitive
    sha256.validate("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    sha512 = Hash(algorithm="sha512")
    sha512.validate(
        "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e"
    )

    with pytest.raises(ValueError):
        md5.validate("zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz")  # bad hex chars
    with pytest.raises(ValueError):
        md5.validate("d41d8cd98f00b204e9800998ecf8427")  # too short
    with pytest.raises(ValueError):
        sha256.validate("d41d8cd98f00b204e9800998ecf8427e")  # md5 length, not sha256
    with pytest.raises(TypeError):
        md5.validate(123)
    with pytest.raises(ValueError):
        Hash(algorithm="bogus")


def test_credit_card_constraint() -> None:
    constraint = CreditCard()
    # Valid Luhn-passing test numbers (industry standard test cards)
    constraint.validate("4111111111111111")  # Visa
    constraint.validate("5555555555554444")  # Mastercard
    constraint.validate("378282246310005")  # Amex (15 digits)
    constraint.validate("4111-1111-1111-1111")  # with dashes
    constraint.validate("4111 1111 1111 1111")  # with spaces

    with pytest.raises(ValueError):
        constraint.validate("4111111111111112")  # bad checksum
    with pytest.raises(ValueError):
        constraint.validate("411111111111")  # too short
    with pytest.raises(ValueError):
        constraint.validate("41111111111111111111")  # too long
    with pytest.raises(ValueError):
        constraint.validate("4111-abcd-1111-1111")  # non-digits
    with pytest.raises(TypeError):
        constraint.validate(4111111111111111)


def test_isbn_constraint() -> None:
    constraint = ISBN()
    # ISBN-10
    constraint.validate("0306406152")
    constraint.validate("0-306-40615-2")
    constraint.validate("043942089X")  # X check char
    # ISBN-13
    constraint.validate("9780306406157")
    constraint.validate("978-0-306-40615-7")

    with pytest.raises(ValueError):
        constraint.validate("0306406151")  # bad ISBN-10 checksum
    with pytest.raises(ValueError):
        constraint.validate("9780306406158")  # bad ISBN-13 checksum
    with pytest.raises(ValueError):
        constraint.validate("12345")  # wrong length
    with pytest.raises(ValueError):
        constraint.validate("030640615A")  # invalid char
    with pytest.raises(ValueError):
        constraint.validate("123456789012X")  # 13 chars but not all digits
    with pytest.raises(TypeError):
        constraint.validate(9780306406157)


def test_hex_string_constraint() -> None:
    constraint = HexString()
    constraint.validate("deadbeef")
    constraint.validate("DEADBEEF")
    constraint.validate("0123456789abcdef")
    with pytest.raises(ValueError):
        constraint.validate("deadbeeg")  # 'g' not hex
    with pytest.raises(ValueError):
        constraint.validate("")  # empty fails (regex requires at least 1)

    fixed = HexString(length=8)
    fixed.validate("deadbeef")
    with pytest.raises(ValueError):
        fixed.validate("dead")  # too short
    with pytest.raises(ValueError):
        fixed.validate("deadbeefcafe")  # too long
    with pytest.raises(ValueError):
        HexString(length=0)
    with pytest.raises(TypeError):
        constraint.validate(123)


def test_timezone_name_constraint() -> None:
    constraint = TimezoneName()
    constraint.validate("America/New_York")
    constraint.validate("Europe/Berlin")
    constraint.validate("UTC")
    constraint.validate("Asia/Tokyo")

    with pytest.raises(ValueError):
        constraint.validate("Not/A/Timezone")
    with pytest.raises(ValueError):
        constraint.validate("America/Atlantis")
    with pytest.raises(TypeError):
        constraint.validate(123)


def test_sorted_constraint() -> None:
    asc = Sorted()
    asc.validate([1, 2, 3, 3, 4])
    asc.validate(["a", "b", "c"])
    asc.validate([])
    asc.validate([42])

    with pytest.raises(ValueError):
        asc.validate([1, 3, 2])
    with pytest.raises(ValueError):
        asc.validate(["b", "a"])

    desc = Sorted(reverse=True)
    desc.validate([5, 4, 3, 3, 1])
    with pytest.raises(ValueError):
        desc.validate([1, 2, 3])

    with pytest.raises(TypeError):
        asc.validate(iter([1, 2, 3]))  # exhaustible iterator
    with pytest.raises(TypeError):
        asc.validate(123)
    with pytest.raises(TypeError):
        asc.validate([1, "a", 2])  # mixed comparison


def test_no_whitespace_constraint() -> None:
    constraint = NoWhitespace()
    constraint.validate("hello")
    constraint.validate("")
    with pytest.raises(ValueError):
        constraint.validate("hello world")
    with pytest.raises(ValueError):
        constraint.validate("a\tb")
    with pytest.raises(ValueError):
        constraint.validate("a\nb")
    with pytest.raises(TypeError):
        constraint.validate(123)


def test_single_line_constraint() -> None:
    constraint = SingleLine()
    constraint.validate("hello world")
    constraint.validate("")
    constraint.validate("a\tb")  # tabs allowed
    with pytest.raises(ValueError):
        constraint.validate("line1\nline2")
    with pytest.raises(ValueError):
        constraint.validate("foo\rbar")
    with pytest.raises(TypeError):
        constraint.validate(123)


def test_printable_singleton() -> None:
    Printable.validate("hello world!")
    Printable.validate("")
    Printable.validate("café 123")
    with pytest.raises(ValueError):
        Printable.validate("control\x00char")
    with pytest.raises(ValueError):
        Printable.validate("with\nnewline")


def test_max_bytes_constraint() -> None:
    constraint = MaxBytes(max_bytes=5)
    constraint.validate("hello")  # 5 bytes
    constraint.validate("abc")
    constraint.validate("")
    constraint.validate(b"hello")  # raw bytes also accepted
    constraint.validate(bytearray(b"abc"))
    with pytest.raises(ValueError):
        constraint.validate("hello!")  # 6 bytes
    with pytest.raises(ValueError):
        constraint.validate("é" * 3)  # 6 UTF-8 bytes (each é is 2)
    with pytest.raises(ValueError):
        constraint.validate(b"hello!")  # 6 raw bytes
    with pytest.raises(ValueError):
        MaxBytes(max_bytes=0)
    with pytest.raises(TypeError):
        constraint.validate(123)


def test_path_safe_constraint() -> None:
    constraint = PathSafe()
    constraint.validate("file.txt")
    constraint.validate("my-document_v2.pdf")
    constraint.validate("photo (1).jpg")
    with pytest.raises(ValueError):
        constraint.validate("")
    with pytest.raises(ValueError):
        constraint.validate(".")
    with pytest.raises(ValueError):
        constraint.validate("..")
    with pytest.raises(ValueError):
        constraint.validate("a/b.txt")  # forward slash
    with pytest.raises(ValueError):
        constraint.validate("a\\b.txt")  # backslash
    with pytest.raises(ValueError):
        constraint.validate("../etc/passwd")  # contains slash
    with pytest.raises(ValueError):
        constraint.validate("file\x00.txt")  # null byte
    with pytest.raises(TypeError):
        constraint.validate(123)


def test_hostname_constraint() -> None:
    constraint = Hostname()
    constraint.validate("localhost")
    constraint.validate("example.com")
    constraint.validate("sub.example.com")
    constraint.validate("a-b-c.example.com")
    constraint.validate("a" * 63 + ".com")  # max label length
    with pytest.raises(ValueError):
        constraint.validate("")
    with pytest.raises(ValueError):
        constraint.validate("-example.com")  # leading hyphen
    with pytest.raises(ValueError):
        constraint.validate("example-.com")  # trailing hyphen
    with pytest.raises(ValueError):
        constraint.validate("a" * 64 + ".com")  # label too long
    with pytest.raises(ValueError):
        constraint.validate("foo..bar")  # empty label
    with pytest.raises(ValueError):
        constraint.validate("foo bar")  # space
    with pytest.raises(TypeError):
        constraint.validate(123)


def test_http_url_constraint() -> None:
    constraint = HttpURL()
    constraint.validate("http://example.com")
    constraint.validate("https://example.com/path?q=1")
    constraint.validate("https://sub.example.com:8080/x")
    with pytest.raises(ValueError):
        constraint.validate("ftp://example.com")
    with pytest.raises(ValueError):
        constraint.validate("file:///etc/passwd")
    with pytest.raises(ValueError):
        constraint.validate("example.com")  # no scheme
    with pytest.raises(ValueError):
        constraint.validate("https://")  # no netloc
    with pytest.raises(ValueError):
        constraint.validate("http://[invalid")  # urlparse raises on malformed IPv6


def test_data_uri_constraint() -> None:
    constraint = DataURI()
    constraint.validate("data:,Hello")
    constraint.validate("data:text/plain,Hello")
    constraint.validate("data:image/png;base64,iVBORw0KGgo")
    constraint.validate("data:application/json;charset=utf-8,{}")
    with pytest.raises(ValueError):
        constraint.validate("data:no-comma")
    with pytest.raises(ValueError):
        constraint.validate("https://example.com")
    with pytest.raises(ValueError):
        constraint.validate("")
    with pytest.raises(TypeError):
        constraint.validate(123)


def test_time_of_day_constraint() -> None:
    constraint = TimeOfDay()
    constraint.validate("00:00")
    constraint.validate("09:30")
    constraint.validate("23:59")
    constraint.validate("12:34:56")
    with pytest.raises(ValueError):
        constraint.validate("24:00")  # hour out of range
    with pytest.raises(ValueError):
        constraint.validate("12:60")  # minute out of range
    with pytest.raises(ValueError):
        constraint.validate("9:30")  # missing leading zero
    with pytest.raises(ValueError):
        constraint.validate("12:34:56.789")  # fractional seconds not allowed
    with pytest.raises(ValueError):
        constraint.validate("noon")
    with pytest.raises(TypeError):
        constraint.validate(123)


def test_pem_block_constraint() -> None:
    constraint = PEMBlock()
    valid_cert = (
        "-----BEGIN CERTIFICATE-----\n"
        "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n"
        "abc123def456\n"
        "-----END CERTIFICATE-----"
    )
    constraint.validate(valid_cert)

    valid_pubkey = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOC\n-----END PUBLIC KEY-----\n"
    constraint.validate(valid_pubkey)

    with pytest.raises(ValueError):
        constraint.validate("not a pem block")
    with pytest.raises(ValueError):
        constraint.validate("-----BEGIN CERTIFICATE-----\nMIIBIjAN\n-----END PUBLIC KEY-----")  # mismatched labels
    with pytest.raises(ValueError):
        constraint.validate("-----BEGIN CERTIFICATE-----\n\n-----END CERTIFICATE-----")  # empty body
    with pytest.raises(TypeError):
        constraint.validate(123)


def test_all_equal_constraint() -> None:
    constraint = AllEqual()
    constraint.validate([])
    constraint.validate([1])
    constraint.validate([1, 1, 1])
    constraint.validate(["a", "a"])
    with pytest.raises(ValueError):
        constraint.validate([1, 2])
    with pytest.raises(ValueError):
        constraint.validate(["a", "b"])
    with pytest.raises(TypeError):
        constraint.validate(iter([1, 1]))
    with pytest.raises(TypeError):
        constraint.validate(123)


def test_non_empty_singleton() -> None:
    NonEmpty.validate("a")
    NonEmpty.validate([1])
    NonEmpty.validate({"k": "v"})
    with pytest.raises(ValueError):
        NonEmpty.validate("")
    with pytest.raises(ValueError):
        NonEmpty.validate([])
    with pytest.raises(ValueError):
        NonEmpty.validate({})


def test_is_tz_aware_singleton() -> None:
    import datetime as dt

    aware = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    aware_pst = dt.datetime(2024, 1, 1, tzinfo=dt.timezone(dt.timedelta(hours=-8)))
    naive = dt.datetime(2024, 1, 1)

    IsTzAware.validate(aware)
    IsTzAware.validate(aware_pst)
    with pytest.raises(ValueError):
        IsTzAware.validate(naive)
    with pytest.raises(ValueError):
        IsTzAware.validate("not a datetime")


def test_is_tz_naive_singleton() -> None:
    import datetime as dt

    naive = dt.datetime(2024, 1, 1)
    aware = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)

    IsTzNaive.validate(naive)
    with pytest.raises(ValueError):
        IsTzNaive.validate(aware)
    with pytest.raises(ValueError):
        IsTzNaive.validate("not a datetime")


def test_decimal_places_constraint() -> None:
    from decimal import Decimal

    constraint = DecimalPlaces(max_places=2)
    constraint.validate(1)
    constraint.validate(1.5)
    constraint.validate(1.25)
    constraint.validate(Decimal("1.50"))
    constraint.validate("1.25")
    constraint.validate("100")
    with pytest.raises(ValueError):
        constraint.validate(1.234)
    with pytest.raises(ValueError):
        constraint.validate(Decimal("1.234"))
    with pytest.raises(ValueError):
        constraint.validate("1.234")
    with pytest.raises(ValueError):
        constraint.validate("not a number")
    with pytest.raises(ValueError):
        DecimalPlaces(max_places=-1)
    with pytest.raises(TypeError):
        constraint.validate(True)
    with pytest.raises(TypeError):
        constraint.validate([1.0])

    zero = DecimalPlaces(max_places=0)
    zero.validate(5)
    zero.validate("100")
    with pytest.raises(ValueError):
        zero.validate(1.5)

    # Scientific notation: round-trips through Decimal
    sci = DecimalPlaces(max_places=2)
    sci.validate("1.5e2")  # = 150, 0 decimal places
    sci.validate("1.5E2")  # uppercase E
    with pytest.raises(ValueError):
        sci.validate("1.5e-3")  # = 0.0015, 4 decimal places


def test_oneof_accepts_enum() -> None:
    import enum

    class Color(enum.Enum):
        RED = "r"
        GREEN = "g"
        BLUE = "b"

    constraint = OneOf(Color)
    # Accept member instances
    constraint.validate(Color.RED)
    constraint.validate(Color.GREEN)
    # Accept underlying values
    constraint.validate("r")
    constraint.validate("g")
    with pytest.raises(ValueError):
        constraint.validate("yellow")
    with pytest.raises(ValueError):
        constraint.validate("RED")  # name, not value


def test_string_constraints_accept_bytes() -> None:
    """String-based constraints accept str, bytes, and bytearray inputs uniformly."""

    # Format / identity
    Email().validate(b"hello@example.com")
    Email().validate(bytearray(b"hello@example.com"))
    PhoneE164().validate(b"+14155552671")
    Hash(algorithm="sha256").validate(b"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    CreditCard().validate(b"4111111111111111")
    ISBN().validate(b"9780306406157")
    HexString().validate(b"deadbeef")
    MimeType().validate(b"application/json")
    DataURI().validate(b"data:text/plain,Hello")

    # Network / regex shapes
    Slug().validate(b"my-blog-post")
    SemVer().validate(b"1.2.3")
    Base64().validate(b"SGVsbG8=")
    HexColor().validate(b"#ff5733")
    MacAddress().validate(b"00:1A:2B:3C:4D:5E")
    JWT().validate(b"eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig")
    Hostname().validate(b"sub.example.com")
    HttpURL().validate(b"https://example.com")
    PathSafe().validate(b"file.txt")

    # Time / cron / CSV
    TimeOfDay().validate(b"09:30")
    TimezoneName().validate(b"America/New_York")
    Cron().validate(b"* * * * *")
    CSV(LowerCase, separator=",").validate(b"a,b,c")
    IsISO8601().validate(b"2024-01-01")
    JSON().validate(b'{"x": 1}')

    # Whitespace / structural
    NoWhitespace().validate(b"hello")
    SingleLine().validate(b"hello world")
    Trimmed().validate(b"hello")

    # Sized / position
    StartsWith("foo").validate(b"foobar")
    EndsWith("bar").validate(b"foobar")
    Match(r"^[a-z]+$").validate(b"abc")


def test_string_constraints_reject_invalid_utf8() -> None:
    """Bytes that aren't valid UTF-8 raise ValueError, not TypeError."""
    bad = b"\xff\xfe\xfd"  # not valid UTF-8

    with pytest.raises(ValueError, match="UTF-8"):
        Email().validate(bad)
    with pytest.raises(ValueError, match="UTF-8"):
        Slug().validate(bad)
    with pytest.raises(ValueError, match="UTF-8"):
        Hostname().validate(bad)


def test_string_constraints_still_reject_non_text() -> None:
    """Non-string, non-bytes types still raise TypeError."""
    from monk.constraints import URL

    with pytest.raises(TypeError):
        Email().validate(123)
    with pytest.raises(TypeError):
        Slug().validate([1, 2, 3])
    with pytest.raises(TypeError):
        Hostname().validate({"x": 1})
    with pytest.raises(TypeError):
        URL().validate(123)
    with pytest.raises(TypeError):
        HttpURL().validate(123)


# --- File upload constraints: FileSize + MagicBytes ---

_PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
_JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 16
_GIF87 = b"GIF87a" + b"\x00" * 16
_GIF89 = b"GIF89a" + b"\x00" * 16
_WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 8
_PDF = b"%PDF-1.4\n" + b"\x00" * 16
_ZIP = b"PK\x03\x04" + b"\x00" * 16
_TAR = b"\x00" * 257 + b"ustar" + b"\x00" * 16
_OGG = b"OggS" + b"\x00" * 16
_BOGUS = b"\xde\xad\xbe\xef" * 8


def test_file_size_constraint() -> None:
    c = FileSize(min_size=4, max_size=8)
    c.validate(b"abcd")
    c.validate(b"abcdefgh")
    c.validate(bytearray(b"abcdef"))
    with pytest.raises(ValueError):
        c.validate(b"abc")  # below min
    with pytest.raises(ValueError):
        c.validate(b"abcdefghi")  # above max
    with pytest.raises(TypeError):
        c.validate("string-not-bytes")
    with pytest.raises(TypeError):
        c.validate(12345)


def test_file_size_bounds_optional() -> None:
    FileSize(max_size=10).validate(b"hi")
    FileSize(min_size=2).validate(b"hi there")
    FileSize().validate(b"any")


def test_magic_bytes_detects_known_formats() -> None:
    c = MagicBytes()
    c.validate(_PNG_HEADER)
    c.validate(_JPEG_HEADER)
    c.validate(_GIF87)
    c.validate(_GIF89)
    c.validate(_WEBP)
    c.validate(_PDF)
    c.validate(_ZIP)
    c.validate(_TAR)
    c.validate(_OGG)


def test_magic_bytes_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="does not match"):
        MagicBytes().validate(_BOGUS)


def test_magic_bytes_allowed_whitelist() -> None:
    c = MagicBytes(allowed=("image/png", "image/jpeg"))
    c.validate(_PNG_HEADER)
    c.validate(_JPEG_HEADER)
    with pytest.raises(ValueError, match="not in allowed types"):
        c.validate(_PDF)


def test_magic_bytes_extra_signatures() -> None:
    custom = b"MYFMT\x00"
    c = MagicBytes(
        allowed=("application/x-myfmt",),
        extra_signatures={"application/x-myfmt": ((custom, 0),)},
    )
    c.validate(custom + b"\x00" * 16)
    with pytest.raises(ValueError):
        c.validate(_PNG_HEADER)


def test_magic_bytes_type_error() -> None:
    with pytest.raises(TypeError):
        MagicBytes().validate("not bytes")
    with pytest.raises(TypeError):
        MagicBytes().validate(123)


def test_magic_bytes_accepts_bytearray() -> None:
    MagicBytes().validate(bytearray(_PNG_HEADER))


def test_file_size_and_magic_bytes_compose() -> None:
    """Both constraints stack on a single field via @monk dataclass."""

    @monk(defer=False)
    class Upload:
        body: Annotated[bytes, MagicBytes(allowed=("image/png",)), FileSize(max_size=64)]

    Upload(body=_PNG_HEADER)
    with pytest.raises(ValidationError):
        Upload(body=_BOGUS)
    with pytest.raises(ValidationError):
        Upload(body=_PNG_HEADER * 4)


def test_magic_bytes_accepts_single_string_allowed() -> None:
    c = MagicBytes(allowed="image/png")
    c.validate(_PNG_HEADER)
    with pytest.raises(ValueError, match="not in allowed types"):
        c.validate(_JPEG_HEADER)


def test_magic_bytes_constructs_with_ref_allowed() -> None:
    # Construction must not eagerly call frozenset(Ref(...)).
    MagicBytes(allowed=Ref("content_type"))
    MagicBytes(allowed=Ctx("allowed_mimes"))


def test_magic_bytes_resolves_ref_to_string_at_validation() -> None:
    @monk
    class Req:
        content_type: Annotated[str, OneOf(("image/png", "image/jpeg"))]
        body: Annotated[bytes, MagicBytes(allowed=Ref("content_type"))]

    validate(Req(content_type="image/png", body=_PNG_HEADER))

    bad = Req(content_type="image/png", body=_JPEG_HEADER)
    with pytest.raises(ValidationError) as exc:
        validate(bad)
    assert any("not in allowed types" in msg for msg in exc.value.flatten())


def test_magic_bytes_resolves_ref_to_iterable_at_validation() -> None:
    @monk
    class Req:
        allowed_types: tuple[str, ...]
        body: Annotated[bytes, MagicBytes(allowed=Ref("allowed_types"))]

    validate(Req(allowed_types=("image/png", "image/jpeg"), body=_JPEG_HEADER))

    with pytest.raises(ValidationError):
        validate(Req(allowed_types=("image/png",), body=_JPEG_HEADER))


def test_magic_bytes_resolves_ctx_at_validation() -> None:
    @monk
    class Req:
        body: Annotated[bytes, MagicBytes(allowed=Ctx("allowed_mimes"))]

    validate(Req(body=_PNG_HEADER), context={"allowed_mimes": ("image/png",)})
    validate(Req(body=_PNG_HEADER), context={"allowed_mimes": "image/png"})

    with pytest.raises(ValidationError):
        validate(Req(body=_JPEG_HEADER), context={"allowed_mimes": ("image/png",)})


def test_magic_bytes_concrete_path_still_uses_prebuilt_set() -> None:
    # Backwards-compat: tuple-of-strings path keeps eager frozenset build.
    c = MagicBytes(allowed=("image/png", "image/jpeg"))
    assert getattr(c, "_allowed_set") == frozenset({"image/png", "image/jpeg"})


def test_magic_bytes_rejects_non_iterable_allowed() -> None:
    with pytest.raises(TypeError, match="expected a mime string or iterable"):
        MagicBytes(allowed=123)  # type: ignore[arg-type]
