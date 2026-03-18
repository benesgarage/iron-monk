import pytest
import uuid
import ipaddress
from monk.constraints import URL, IPAddress, UUID


def test_url_constraint() -> None:
    URL().validate("url", "https://example.com")
    URL().validate("url", None)

    with pytest.raises(ValueError):
        URL().validate("url", "not-a-url")
    with pytest.raises(ValueError):
        URL().validate("url", "http://")  # No network location


def test_ipaddress_constraint() -> None:
    IPAddress().validate("ip", "192.168.1.1")
    IPAddress().validate("ip", "2001:db8::")
    IPAddress().validate("ip", ipaddress.ip_address("192.168.1.1"))  # Native object
    IPAddress().validate("ip", None)

    with pytest.raises(ValueError):
        IPAddress().validate("ip", "256.256.256.256")


def test_uuid_constraint() -> None:
    UUID().validate("id", "123e4567-e89b-12d3-a456-426614174000")
    UUID().validate("id", uuid.uuid4())  # Native object
    UUID().validate("id", None)

    with pytest.raises(ValueError):
        UUID().validate("id", "not-a-uuid")
