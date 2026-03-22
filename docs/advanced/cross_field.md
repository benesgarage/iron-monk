# Cross-Field Validation

Use the `__monk_validate__` hook for rules that depend on multiple fields. It runs automatically, but only after all individual field constraints pass.

You can `yield` multiple errors (as an iterator) or `return` a single error. Errors can be strings (for model-wide errors) or tuples (for field-specific errors).

```python
from collections.abc import Iterator
from monk import monk
from monk.types import MonkError

@monk
class Registration:
    password: str
    password_confirm: str
    age: int

    def __monk_validate__(self) -> Iterator[MonkError] | None:
        # String: Model-wide "root" error
        if self.password == "admin" and self.age < 18:
            yield "Young users cannot use the admin password."
            
        # 2-Tuple: (field, message)
        if self.password != self.password_confirm:
            yield "password_confirm", "Passwords do not match."
        
        # 3-Tuple: (field, message, code)
        if self.password == "superuser" and self.age < 21:
            yield "age", "Superusers must be over 21", "YoungSuperUser"

@monk 
class Login:
    username: str

    def __monk_validate__(self) -> MonkError | None:
        # Return a single error instantly
        if self.username == "admin":
            return "Admin login is disabled."
```