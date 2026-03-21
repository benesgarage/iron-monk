import pytest
import uuid
import ipaddress
from monk.constraints import URL, IPAddress, UUID


def test_url_constraint() -> None:
    URL().validate("https://example.com")

    with pytest.raises(ValueError):
        URL().validate("not-a-url")
    with pytest.raises(ValueError):
        URL().validate("http://")  # No network location


def test_ipaddress_constraint() -> None:
    IPAddress().validate("192.168.1.1")
    IPAddress().validate("2001:db8::")
    IPAddress().validate(ipaddress.ip_address("192.168.1.1"))  # Native object

    with pytest.raises(ValueError):
        IPAddress().validate("256.256.256.256")


def test_uuid_constraint() -> None:
    UUID().validate("123e4567-e89b-12d3-a456-426614174000")
    UUID().validate(uuid.uuid4())  # Native object

    with pytest.raises(ValueError):
        UUID().validate("not-a-uuid")
