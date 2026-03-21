import pytest
from typing import Iterator, AsyncIterator
from monk import validate_stream, validate_async_stream
from monk.constraints import Email, EndsWith
from monk.exceptions import ValidationError


def test_sync_stream_validation() -> None:
    def stream() -> Iterator[str]:
        yield "test@domain.com"
        yield "admin@domain.com"
        yield "bad-email"

    gen = validate_stream(stream(), Email)

    assert next(gen) == "test@domain.com"
    assert next(gen) == "admin@domain.com"

    with pytest.raises(ValidationError) as exc:
        next(gen)

    assert exc.value.errors[0]["field"] == "[2]"
    assert exc.value.errors[0]["code"] == "Email"


def test_sync_stream_multiple_constraints() -> None:
    def stream() -> Iterator[str]:
        yield "test@domain.com"
        yield "hacker@evil.com"

    # Passing an uninstantiated class AND an instantiated class with args
    gen = validate_stream(stream(), Email, EndsWith("@domain.com"))

    assert next(gen) == "test@domain.com"

    with pytest.raises(ValidationError) as exc:
        next(gen)

    assert exc.value.errors[0]["field"] == "[1]"
    assert exc.value.errors[0]["code"] == "EndsWith"


@pytest.mark.anyio
async def test_async_stream_multiple_constraints() -> None:
    async def async_stream() -> AsyncIterator[str]:
        yield "test@domain.com"
        yield "hacker@evil.com"

    gen = validate_async_stream(async_stream(), Email, EndsWith("@domain.com"))

    assert await anext(gen) == "test@domain.com"

    with pytest.raises(ValidationError) as exc:
        await anext(gen)

    assert exc.value.errors[0]["field"] == "[1]"
    assert exc.value.errors[0]["code"] == "EndsWith"


@pytest.mark.anyio
async def test_async_stream_validation() -> None:
    async def async_stream() -> AsyncIterator[str]:
        yield "test@domain.com"
        yield "admin@domain.com"
        yield "bad-email"

    gen = validate_async_stream(async_stream(), Email)

    assert await anext(gen) == "test@domain.com"
    assert await anext(gen) == "admin@domain.com"

    with pytest.raises(ValidationError) as exc:
        await anext(gen)

    assert exc.value.errors[0]["field"] == "[2]"
    assert exc.value.errors[0]["code"] == "Email"
