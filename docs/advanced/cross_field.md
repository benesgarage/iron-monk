# Cross-Field Validation

Sometimes a validation rule depends on multiple fields at once (e.g., `password` must equal `password_confirm`, or `end_date` must be after `start_date`).

To handle this, `iron-monk` provides the `__monk_validate__` hook. This method is executed automatically only if all individual field-level constraints pass successfully.

```python
from collections.abc import Iterator

from monk import monk
from monk.types import MonkError

# 1. Return an iterator, this can be any iterable (list, generator, etc.)
@monk
class Registration:
    password: str
    password_confirm: str
    age: int

    def __monk_validate__(self) -> Iterator[MonkError] | None:
        # String (or 1-Tuple) for a model-wide "root" error
        if self.password == "admin" and self.age < 18:
            yield "Young users cannot use the admin password."
            
        # 2-Tuple (field, message)
        if self.password != self.password_confirm:
            yield "password_confirm", "Passwords do not match."
        
        # 3-Tuple (field, message, constraint_name)
        if self.password == "superuser" and self.age < 21:
            yield "age", "Superusers must be over 21", "YoungSuperUser"


# 2. Return a string
@monk 
class Login:
    username: str

    def __monk_validate__(self) -> MonkError | None:
        if self.username == "admin":
            return "Admin login is disabled."
```