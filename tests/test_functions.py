import pytest
from typing import Annotated, Iterator
from monk import monk
from monk.constraints import Email, Interval, Len, Nullable, LowerCase, Each
from monk.exceptions import ValidationError


def test_sync_function_validation() -> None:
    @monk
    def register_user(email: Annotated[str, Email], age: Annotated[int, Interval(ge=18)]) -> str:
        return f"Registered {email}"

    # 1. Success
    assert register_user("test@domain.com", 25) == "Registered test@domain.com"
    assert register_user(email="test@domain.com", age=25) == "Registered test@domain.com"

    # 2. Failure aggregates correctly
    with pytest.raises(ValidationError) as exc:
        register_user("bad-email", 12)

    errors = exc.value.errors
    assert len(errors) == 2
    assert errors[0]["field"] == "email"
    assert errors[0]["code"] == "Email"
    assert errors[1]["field"] == "age"
    assert errors[1]["code"] == "Interval"


@pytest.mark.anyio
async def test_async_function_validation() -> None:
    @monk
    async def fetch_data(url: Annotated[str, Len(min_len=10)]) -> bool:
        return True

    assert await fetch_data("https://github.com") is True

    with pytest.raises(ValidationError) as exc:
        await fetch_data("bad")

    assert exc.value.errors[0]["field"] == "url"
    assert exc.value.errors[0]["code"] == "Len"


def test_function_nullability() -> None:
    @monk
    def process_data(
        required_tag: Annotated[str, Len(min_len=3)],
        optional_tag: Annotated[str | None, Nullable, Len(min_len=3)] = None,
    ) -> None:
        pass

    # Missing required field
    with pytest.raises(ValidationError) as exc:
        process_data(required_tag=None)  # type: ignore
    assert exc.value.errors[0]["code"] == "NotNull"

    # Safely skipping explicitly nullable field
    process_data(required_tag="core")


def test_method_validation() -> None:
    class Processor:
        @monk
        def process_instance(self, data: Annotated[str, Len(min_len=3)]) -> str:
            return data

        @classmethod
        @monk
        def process_class(cls, data: Annotated[str, Len(min_len=3)]) -> str:
            return data

        @staticmethod
        @monk
        def process_static(data: Annotated[str, Len(min_len=3)]) -> str:
            return data

    p = Processor()

    # 1. Instance Method
    assert p.process_instance("abc") == "abc"
    with pytest.raises(ValidationError) as exc:
        p.process_instance("ab")
    assert exc.value.errors[0]["field"] == "data"

    # 2. Class Method
    with pytest.raises(ValidationError) as exc:
        Processor.process_class("ab")
    assert exc.value.errors[0]["field"] == "data"

    # 3. Static Method
    with pytest.raises(ValidationError) as exc:
        Processor.process_static("ab")
    assert exc.value.errors[0]["field"] == "data"


def test_sync_function_return_validation() -> None:
    @monk
    def process_data(data: str) -> Annotated[str, LowerCase]:
        return data

    # Success
    assert process_data("hello") == "hello"

    # Failure
    with pytest.raises(ValidationError) as exc:
        process_data("HELLO")

    assert exc.value.errors[0]["field"] == "return"
    assert exc.value.errors[0]["code"] == "Predicate"


@pytest.mark.anyio
async def test_async_function_return_validation() -> None:
    @monk
    async def fetch_data() -> Annotated[dict[str, str], Len(min_len=1)]:
        return {}

    with pytest.raises(ValidationError) as exc:
        await fetch_data()

    assert exc.value.errors[0]["field"] == "return"
    assert exc.value.errors[0]["code"] == "Len"


def test_function_generator_consumption_protection() -> None:
    @monk
    def process_stream(stream: Annotated[Iterator[str], Each(LowerCase)]) -> list[str]:
        return list(stream)

    gen = (x for x in ["a", "b"])

    with pytest.raises(ValidationError) as exc:
        process_stream(gen)

    assert "Cannot eagerly validate exhaustible iterator" in exc.value.errors[0]["message"]
