import pytest
from typing import Annotated
from monk import monk, validate
from monk.constraints import Len, Interval, Each
from monk.exceptions import ValidationError


def test_tyro_integration() -> None:
    import tyro

    @monk
    class CLIArgs:
        tags: Annotated[list[str], Each(Len(min_len=3))]
        max_warnings: Annotated[int, Interval(ge=0)] = 10

    args = tyro.cli(CLIArgs, args=["--tags", "abc", "def", "--max-warnings", "5"])
    valid_args = validate(args)
    assert valid_args.max_warnings == 5
    assert valid_args.tags == ["abc", "def"]

    bad_args = tyro.cli(CLIArgs, args=["--tags", "a", "def"])
    with pytest.raises(ValidationError) as exc:
        validate(bad_args)

    assert exc.value.errors[0]["field"] == "tags[0]"
