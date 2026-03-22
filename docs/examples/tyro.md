# CLI Tools (tyro)

> https://github.com/brentyi/tyro

`tyro` generates command-line interfaces directly from type hints. Because `iron-monk` uses standard dataclasses without heavy metaclasses, they pair flawlessly: `tyro` parses the inputs, and `iron-monk` enforces the business rules.

```python
import sys
import tyro
import pathlib
from typing import Annotated

from monk import monk, validate
from monk.constraints import NonNegative, OneOf, Each, Len, IsDir
from monk.exceptions import ValidationError

@monk
class CLIArgs:
    target_dir: Annotated[pathlib.Path, IsDir]
    tags: Annotated[list[str], Each(Len(min_len=3))]
    max_warnings: Annotated[int, NonNegative] = 10
    output_format: Annotated[str, OneOf(["json", "text", "html"])] = "text"

def main():
    # 1. tyro parses sys.argv and builds the dataclass
    args = tyro.cli(CLIArgs)

    # 2. iron-monk validates the logic
    try:
        valid_args = validate(args)
    except ValidationError as e:
        print("❌ Invalid arguments provided:\n", file=sys.stderr)
        for err in e.errors:
            print(f"  --{err['field'].replace('_', '-')}: {err['message']}", file=sys.stderr)
        sys.exit(1)

    print(f"✅ Linting target: {valid_args.target_dir}")

if __name__ == "__main__":
    main()
```

### Output
```bash
$ python cli_tyro.py --target-dir not-a-path --max-warnings -1 --tags john kelly smith bo --output-format yml

❌ Invalid arguments provided:

  --target-dir: Must be an existing directory.
  --tags[3]: Must have a minimum length of 3.
  --max-warnings: Must be greater than or equal to 0.
  --output-format: Must be one of: ['json', 'text', 'html'], got 'yml'.
```