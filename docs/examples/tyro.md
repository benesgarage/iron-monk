# CLI Tools (tyro)

`tyro` is a CLI generation framework that relies entirely on native Python type hints to generate beautiful terminal interfaces. 

Because `iron-monk` does not pollute dataclasses with custom metaclasses, the two tools work together flawlessly. `tyro` acts as the parser (casting strings to integers and paths), and `iron-monk` acts as the enforcer (validating the business logic rules).

```python
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
    except ValidationError as e:
        print("❌ Invalid arguments provided:\n", file=sys.stderr)
        for err in e.errors:
            print(f"  --{err['field'].replace('_', '-')}: {err['message']}", file=sys.stderr)
    
    print(f"Linting target: {valid_args.target_dir}")

if __name__ == "__main__":
    main()
```

### Output
```bash
cli_tyro.py --target-dir not-a-path --max-warnings -1 --tags john kelly smith bo --output-format yml
❌ Invalid arguments provided:

  --target-dir: Must be an existing directory.
  --tags[3]: Must have a minimum length of 3.
  --max-warnings: Must be greater than or equal to 0.
  --output-format: Must be one of: ['json', 'text', 'html'], got 'yml'.
```