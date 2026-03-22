# Logical Composability

Use logical constraints to handle complex inputs and group error messages.

- `AnyOf` (OR): Passes if at least one constraint succeeds. Perfect for fields that accept multiple formats.
- `AllOf` (AND): Enforces that all constraints pass. Used to group multiple rules under a single custom error message or code.
- `Not` (NOT): Inverts a constraint. Succeeds only if the inner rule fails.

### Nested Composability
Because these operators are standard constraints, you can deeply nest them to represent complex real-world business logic.
```python
from typing import Annotated
from monk import monk
from monk.constraints import AnyOf, AllOf, Not, Email, StartsWith, LowerCase, Len, EndsWith

@monk
class ComplexRules:
    # 1. AnyOf (OR): Email OR Phone
    identifier: Annotated[
        str, 
        AnyOf(Email, StartsWith("+"), message="Must be an email or phone number.")
    ]

    # 2. AllOf (AND): Groups rules under one unified message
    username: Annotated[
        str, 
        AllOf(LowerCase, Len(min_len=5), message="Usernames must be lowercase and 5+ chars.")
    ]

    # 3. Not (NOT): Fails if the password IS entirely lowercase
    password: Annotated[
        str, 
        Not(LowerCase, message="Password cannot be entirely lowercase.")
    ]

    # 4. Nested: Matches Email OR (Phone AND length <= 15 AND NOT ending in "000")
    contact: Annotated[
        str,
        AnyOf(
            Email,
            AllOf(StartsWith("+"), Len(max_len=15), Not(EndsWith("000")))
        )
    ]
```