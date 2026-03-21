# Tortoise ORM

Unlike SQLAlchemy 2.0 (which natively supports standard Python dataclasses), [Tortoise ORM](https://tortoise.github.io/) is an Active Record framework inspired by Django. It uses a heavy custom metaclass and tightly controls its own `__init__` method.

Because of this, you should **not** decorate Tortoise models directly with `@monk` (or any standard dataclass decorator).

Instead, `iron-monk` pairs beautifully with Tortoise using the **DTO (Data Transfer Object)** pattern. This creates a strict boundary between your API Validation layer and your Database Persistence layer.

## The Integration

```python
import dataclasses
from typing import Annotated
from tortoise.models import Model
from tortoise import fields

from monk import monk, validate
from monk.constraints import Email, Len
from monk.exceptions import ValidationError

# 1. Persistence Layer: The Tortoise ORM Model
class UserDB(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    email = fields.CharField(max_length=255, unique=True)

    class Meta:
        table = "users"

# 2. Validation Layer: The iron-monk DTO
@monk
class CreateUserPayload:
    username: Annotated[str, Len(min_len=3, max_len=50)]
    email: Annotated[str, Email]

# 3. The Business Logic
async def register_user(raw_json: dict) -> UserDB | None:
    try:
        # Validate the incoming data BEFORE it ever touches the ORM
        payload = validate(CreateUserPayload(**raw_json))
    except ValidationError as e:
        print("Validation failed:", e.flatten())
        return None

    # Safely pass the validated data to Tortoise ORM
    # We use dataclasses.asdict() to easily unpack the safe payload.
    user = await UserDB.create(**dataclasses.asdict(payload))
    print(f"Created user safely with ID: {user.id}")
    
    return user

# Try it!
register_user({"username": "bo", "email": "not-an-email"})
# Validation failed: ['username: Must have a minimum length of 3.', 'email: Must be a valid email address.']
```