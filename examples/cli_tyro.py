import sys
import tyro
import pathlib
from typing import Annotated

from monk import monk, validate
from monk.constraints import NonNegative, OneOf, Each, Len, IsDir
from monk.exceptions import ValidationError


# 1. Define your CLI arguments schema
# iron-monk and tyro both natively understand dataclasses
@monk
class CLIArgs:
    """A strictly validated CLI tool."""

    target_dir: Annotated[pathlib.Path, IsDir]
    tags: Annotated[list[str], Each(Len(min_len=3))]
    max_warnings: Annotated[int, NonNegative] = 10
    output_format: Annotated[str, OneOf(["json", "text", "html"])] = "text"


def main():
    # tyro automatically generates the CLI, parses sys.argv, and instantiates the dataclass
    args = tyro.cli(CLIArgs)

    try:
        # iron-monk strictly validates the instantiated dataclass
        valid_args = validate(args)

        print("✅ Arguments parsed and validated successfully!")
        print(f"   Target: {valid_args.target_dir}")
        print(f"   Max Warnings: {valid_args.max_warnings}")
        print(f"   Tags: {valid_args.tags}")
        print(f"   Output format: {valid_args.output_format}")

    except ValidationError as e:
        print("❌ Invalid arguments provided:\n", file=sys.stderr)
        for err in e.errors:
            print(f"  --{err['field'].replace('_', '-')}: {err['message']}", file=sys.stderr)


# Run the script:
# cli_tyro.py --target-dir not-a-path --max-warnings -1 --tags john kelly smith bo --output-format yml
# ❌ Invalid arguments provided:
#
#   --target-dir: Must be an existing directory.
#   --tags[3]: Must have a minimum length of 3.
#   --max-warnings: Must be greater than or equal to 0.
#   --output-format: Must be one of: ['json', 'text', 'html'], got 'yml'.

if __name__ == "__main__":
    main()
