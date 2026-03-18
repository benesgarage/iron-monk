# The Constraint Toolkit

`iron-monk` comes with a comprehensive suite of built-in constraints. You apply them using `typing.Annotated`.

> **💡 Tip:** Every single constraint listed below accepts an optional `message` argument for Custom Error Messages!

## Strings
- `LowerCase` / `UpperCase`: Enforces case strictness.
- `IsDigit` / `IsAscii`: Standard string predicates.

```python
from typing import Annotated
from monk import monk
from monk.constraints import Match, StartsWith, EndsWith

@monk
class Product:
    # Match a specific Regular Expression
    sku: Annotated[str, Match(r"^PROD-\d+$")]
    
    # Check string boundaries
    category_id: Annotated[str, StartsWith("cat_")]
    avatar_file: Annotated[str, EndsWith(".png")]
```

## Numeric
- `NonNegative`: A shortcut for `Interval(ge=0)`.
- `IsFinite`, `IsNan`, `IsInfinite`: Mathematical checks.

```python
from typing import Annotated
from monk import monk
from monk.constraints import Interval, MultipleOf

@monk
class BatchOrder:
    # Define strict or inclusive boundaries (gt, ge, lt, le)
    quantity: Annotated[int, Interval(gt=0, le=100)]
    
    # Ensure the value is perfectly divisible
    pack_size: Annotated[int, MultipleOf(5)]
```

## Collections
- `Contains(item)`: Ensures an item exists in the collection.

```python
from typing import Annotated
from monk import monk
from monk.constraints import Each, LowerCase, Len, OneOf, Unique

@monk
class UserGroups:
    # Ensure the value is exactly one of the provided choices
    role: Annotated[str, OneOf(["admin", "editor", "viewer"])]
    
    # Every string in the list must be lowercase AND at least 3 characters long
    tags: Annotated[list[str], Each(LowerCase, Len(min_len=3))]
    
    # All elements must be unique (safely falls back for unhashable types like lists of lists!)
    matrix: Annotated[list[list[int]], Unique]
```

## Format & Network
- `Email`: Validates using a highly robust structural regex.
- `URL`: Ensures a valid scheme and network location.
- `IPAddress`: Validates IPv4 or IPv6 addresses.
- `UUID`: Validates UUID strings or native UUID objects.

## Logic & File System
- `Predicate(func)`: Validates that a value returns `True` for a given function.
- `Not(constraint)`: Inverts the logic of another constraint.
- `IsUTC`: Ensures a `datetime` object is strictly UTC.
- `IsDir` / `IsFile`: Validates that a string or `pathlib.Path` exists on the filesystem.

```python
import pathlib
from typing import Annotated
from monk import monk
from monk.constraints import Predicate, Not, IsFile, IsDir, LowerCase

def is_even(n: int) -> bool:
    return n % 2 == 0

@monk
class SystemConfig:
    # Invert the logic of any constraint (Fails if the string IS lowercase)
    password: Annotated[str, Not(LowerCase)]
    
    # Validate using any custom function that returns a boolean
    batch_size: Annotated[int, Predicate(is_even)]
    
    # Validate that a string or pathlib.Path actually exists on the filesystem
    config_file: Annotated[pathlib.Path, IsFile]
    output_dir: Annotated[str, IsDir]
```

## Custom Error Messages & Interpolation
Every built-in constraint supports an optional message argument to override the default error string. `iron-monk` uses safe string formatting to allow you to dynamically inject the invalid `{value}` or constraint parameters!
You can even interpolate properties of an inner constraint when using `Not` by accessing `{constraint.property_name}`.

```python
from typing import Annotated

from monk import monk
from monk.constraints import Interval, Not

@monk
class GameSettings:
    # 1. Simple interpolation with {value} and constraint parameters like {ge}
    min_page: Annotated[int, Interval(ge=18, message="You are {value}, but must be at least {ge}!")]
    # 2. Nested interpolation (interpolating properties of the inner constraint)
    forbidden_number: Annotated[
        int, 
        Not(
            Interval(ge=5, le=10), 
            message="You picked {value}, but numbers between {constraint.ge} and {constraint.le} are forbidden!"
        )
    ]
```