import pytest
from typing import Annotated, Any
from collections.abc import Iterator
from monk import monk, validate
from monk.constraints import Interval
from monk.exceptions import ValidationError
from monk.types import MonkError


def test_cross_field_return_string() -> None:
    @monk
    class Model:
        def __monk_validate__(self) -> MonkError:
            return "This is a root error."

    with pytest.raises(ValidationError) as exc:
        validate(Model())
    assert exc.value.errors[0] == {"field": "__root__", "message": "This is a root error.", "constraint": "ModelRule"}


def test_cross_field_return_tuples() -> None:
    @monk
    class Model1:
        def __monk_validate__(self) -> MonkError:
            return ("Just a message",)

    @monk
    class Model2:
        def __monk_validate__(self) -> MonkError:
            return ("password", "Mismatch")

    @monk
    class Model3:
        def __monk_validate__(self) -> MonkError:
            return ("password", "Mismatch", "CustomRule")

    with pytest.raises(ValidationError) as exc1:
        validate(Model1())
    assert exc1.value.errors[0] == {"field": "__root__", "message": "Just a message", "constraint": "ModelRule"}

    with pytest.raises(ValidationError) as exc2:
        validate(Model2())
    assert exc2.value.errors[0] == {"field": "password", "message": "Mismatch", "constraint": "ModelRule"}

    with pytest.raises(ValidationError) as exc3:
        validate(Model3())
    assert exc3.value.errors[0] == {"field": "password", "message": "Mismatch", "constraint": "CustomRule"}


def test_cross_field_yield_mixed() -> None:
    @monk
    class Model:
        def __monk_validate__(self) -> Iterator[MonkError]:
            yield "Root error"
            yield ("password", "Mismatch")
            yield ("age", "Too young", "AgeRule")

    with pytest.raises(ValidationError) as exc:
        validate(Model())

    errors = exc.value.errors
    assert len(errors) == 3
    assert errors[0] == {"field": "__root__", "message": "Root error", "constraint": "ModelRule"}
    assert errors[1] == {"field": "password", "message": "Mismatch", "constraint": "ModelRule"}
    assert errors[2] == {"field": "age", "message": "Too young", "constraint": "AgeRule"}


def test_cross_field_return_list() -> None:
    @monk
    class Model:
        def __monk_validate__(self) -> list[MonkError]:
            # Some developers prefer appending to a list and returning it
            return [
                "Root error",
                ("password", "Mismatch"),
            ]

    with pytest.raises(ValidationError) as exc:
        validate(Model())
    assert len(exc.value.errors) == 2


def test_cross_field_skip_on_field_errors() -> None:
    @monk
    class Model:
        age: Annotated[int, Interval(ge=18)]

        def __monk_validate__(self) -> Iterator[MonkError]:
            # If iron-monk didn't skip this, this line would crash because age is a string!
            if self.age > 21:
                yield "Too old."

    with pytest.raises(ValidationError) as exc:
        validate(Model(age="eighteen"))  # type: ignore[arg-type]

    # We only get the field-level error; the cross-field hook was safely skipped!
    assert len(exc.value.errors) == 1
    assert exc.value.errors[0]["constraint"] == "Interval"


def test_invalid_returns() -> None:
    @monk
    class BadTuple:
        def __monk_validate__(self) -> Any:
            return ("one", "two", "three", "four")

    @monk
    class BadType:
        def __monk_validate__(self) -> Any:
            return 123

    with pytest.raises(TypeError, match="Invalid tuple length"):
        validate(BadTuple())
    with pytest.raises(TypeError, match="Expected a string or tuple"):
        validate(BadType())


def test_cross_field_empty_returns() -> None:
    @monk
    class EmptyList:
        def __monk_validate__(self) -> list[MonkError]:
            return []

    @monk
    class EmptyTuple:
        def __monk_validate__(self) -> tuple[MonkError, ...]:
            return ()

    @monk
    class JustPass:
        def __monk_validate__(self) -> None:
            return None

    # All should validate successfully without raising any errors or TypeErrors
    validate(EmptyList())
    validate(EmptyTuple())
    validate(JustPass())


def test_invalid_items_inside_iterable() -> None:
    @monk
    class BadGenerator:
        def __monk_validate__(self) -> Iterator[Any]:
            yield "This is fine"
            yield 123

    with pytest.raises(TypeError, match="Invalid item yielded/returned"):
        validate(BadGenerator())


def test_invalid_tuple_items_type_error() -> None:
    @monk
    class BadTupleItems:
        def __monk_validate__(self) -> Iterator[Any]:
            yield ("password", 123)

    with pytest.raises(TypeError, match="All tuple items must be strings"):
        validate(BadTupleItems())


def test_cross_field_inheritance() -> None:
    class BaseEvent:
        def __monk_validate__(self) -> Iterator[MonkError]:
            yield "Base error"

    @monk
    class SubEvent(BaseEvent):
        def __monk_validate__(self) -> Iterator[MonkError]:
            # Standard Python generator delegation!
            if hasattr(super(), "__monk_validate__"):
                yield from super().__monk_validate__()
            yield "Sub error"

    with pytest.raises(ValidationError) as exc:
        validate(SubEvent())

    errors = exc.value.errors
    assert len(errors) == 2
    assert errors[0]["message"] == "Base error"
    assert errors[1]["message"] == "Sub error"
