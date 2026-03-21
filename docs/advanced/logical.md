# Logical Composability

`iron-monk` provides dedicated logical constraints for complex input types and advanced message grouping.

### `AnyOf` (Logical OR)
`AnyOf` is perfect when a field accepts multiple valid formats, such as a generic login identifier.

```python
from typing import Annotated
from monk import monk
from monk.constraints import AnyOf, Email, StartsWith

@monk
class LoginPayload:
    # Passes if the value is an Email OR starts with a "+"
    identifier: Annotated[
        str, 
        AnyOf(Email, StartsWith("+"), message="Must be a valid email or phone number.")
    ]
```

### `AllOf` (Logical AND)
`AllOf` enforces that all constraints pass. While standard `Annotated` stacking does this implicitly, `AllOf` allows you to group multiple constraints under a **single custom error message** or **custom error code**.

```python
from typing import Annotated
from monk import monk
from monk.constraints import AllOf, LowerCase, Len

@monk
class Registration:
    # Instead of failing with "Must have a minimum length..." or "Failed validation for islower...",
    # it groups the rules and fails uniformly with your custom message!
    username: Annotated[
        str, 
        AllOf(LowerCase, Len(min_len=5), message="Usernames must be lowercase and 5+ chars.")
    ]
```

### Not (Logical NOT)
The Not constraint inverts the logic of another constraint. It succeeds only if the inner constraint fails.
```python
from typing import Annotated
from monk import monk
from monk.constraints import Not, LowerCase

@monk
class SecurityPayload:
    # Fails if the password IS entirely lowercase
    password: Annotated[
        str, 
        Not(LowerCase, message="Password cannot be entirely lowercase.")
    ]
```

### Nested Composability
Because these logical operators are just standard constraints, they can be deeply nested inside each other to represent complex, real-world business logic.

```python
from typing import Annotated
from monk import monk
from monk.constraints import AnyOf, AllOf, Email, StartsWith, Len, EndsWith


@monk
class ContactInfo:
    # Matches an Email OR Phone number (Starts with "+" AND len <= 15 AND NOT Ends with "000")
    identifier: Annotated[
        str,
        AnyOf(
            Email,
            AllOf(StartsWith("+"), Len(max_len=15), Not(EndsWith("000")))
        )
    ]
```