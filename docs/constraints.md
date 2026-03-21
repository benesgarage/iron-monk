# The Constraint Toolkit

`iron-monk` comes with a comprehensive suite of built-in constraints. You apply them using `typing.Annotated`.

> **💡 Tip:** Every single constraint listed below accepts an optional `message` argument for Custom Error Messages!

## Strings

```python
from typing import Annotated
from monk import monk
from monk.constraints import Match, StartsWith, EndsWith, LowerCase, UpperCase, IsDigit, IsAscii

@monk
class StringConstraints:
    # Enforces case strictness
    lower: Annotated[str, LowerCase]
    upper: Annotated[str, UpperCase]
    
    # Standard string predicates
    pin: Annotated[str, IsDigit]
    ascii_text: Annotated[str, IsAscii]
    
    # Match a specific Regular Expression
    sku: Annotated[str, Match(r"^PROD-\d+$")]
    
    # Check string boundaries
    category_id: Annotated[str, StartsWith("cat_")]
    avatar_file: Annotated[str, EndsWith(".png")]
```

## Numeric

```python
from typing import Annotated

from monk import monk
from monk.constraints import Interval, MultipleOf, NonNegative, IsFinite, IsNan, IsInfinite

@monk
class NumericConstraints:
    # Define strict or inclusive boundaries (gt, ge, lt, le)
    quantity: Annotated[int, Interval(gt=0, le=100)]
    
    # A shortcut for Interval(ge=0)
    score: Annotated[int, NonNegative]

    # Ensure the value is perfectly divisible
    pack_size: Annotated[int, MultipleOf(5)]
    
    # Mathematical checks (usually for floats)
    finite_val: Annotated[float, IsFinite]
    nan_val: Annotated[float, IsNan]
    inf_val: Annotated[float, IsInfinite]
```

## Collections

```python
from typing import Annotated, TypedDict

from monk import monk
from monk.constraints import Each, LowerCase, Len, OneOf, Unique, Contains, Nested

class AddressDict(TypedDict):
    city: str

@monk
class CollectionConstraints:
    # Validates the length of lists, strings, or dicts
    tags: Annotated[list[str], Len(min_len=1, max_len=10)]

    # Ensures an item exists in the collection
    categories: Annotated[list[str], Contains("default")]
    
    # Ensure the value is exactly one of the provided choices
    role: Annotated[str, OneOf(["admin", "editor", "viewer"])]
    
    # All elements must be unique (safely falls back for unhashable types like lists of lists!)
    matrix: Annotated[list[list[int]], Unique]
    
    # Recursively applies constraints to every item in an iterable
    emails: Annotated[list[str], Each(LowerCase, Len(min_len=5))]
    
    # Validates a nested raw dictionary against another schema
    address: Annotated[AddressDict, Nested(AddressDict)]
```

## Format & Network

```python
import uuid
from typing import Annotated

from monk import monk
from monk.constraints import Email, URL, IPAddress, UUID

@monk
class NetworkConstraints:
    # Validates using a highly robust structural regex
    admin_email: Annotated[str, Email]

    # Ensures a valid scheme and network location
    webhook_url: Annotated[str, URL]
    
    # Validates IPv4 or IPv6 addresses
    ip_addr: Annotated[str, IPAddress]
    
    # Validates UUID strings or native UUID objects
    node_id: Annotated[str | uuid.UUID, UUID]
```

## Logic & File System

```python
import datetime
import pathlib
from typing import Annotated

from monk import monk
from monk.constraints import Predicate, Not, IsFile, IsDir, LowerCase, IsUTC

def is_even(n: int) -> bool:
    return n % 2 == 0

@monk
class SystemConfig:
    # Validate using any custom function that returns a boolean
    batch_size: Annotated[int, Predicate(is_even)]

    # Invert the logic of any constraint (Fails if the string IS lowercase)
    password: Annotated[str, Not(LowerCase)]
    
    # Ensures a datetime object is strictly UTC
    created_at: Annotated[datetime.datetime, IsUTC]
    
    # Validate that a string or pathlib.Path actually exists on the filesystem
    config_file: Annotated[pathlib.Path, IsFile]
    output_dir: Annotated[str, IsDir]
```
