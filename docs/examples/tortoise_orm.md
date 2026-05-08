# Tortoise ORM

Tortoise ORM uses custom metaclasses and tightly controls its initialization. Do not decorate Tortoise models directly with `@monk`. Use the DTO (Data Transfer Object) pattern instead — it gives you a clean boundary between API validation and database persistence.

Project: <https://github.com/tortoise/tortoise-orm>

## The integration

```python
import dataclasses
from typing import Annotated
from tortoise.models import Model
from tortoise import fields
from monk import monk, validate
from monk.constraints import Email, Len
from monk.exceptions import ValidationError

# 1. The Database Model (Pure Persistence)
class UserDB(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    email = fields.CharField(max_length=255, unique=True)

    class Meta:
        table = "users"

# 2. The DTO (Pure Validation)
@monk
class CreateUserDTO:
    username: Annotated[str, Len(min_len=3, max_len=50)]
    email: Annotated[str, Email]

# 3. The API / Service Handler
async def register_user(payload: dict) -> UserDB:
    try:
        # Validate at the boundary before touching the ORM
        safe_dto = validate(CreateUserDTO(**payload))
    except ValidationError as e:
        print("Request rejected:", e.flatten())
        raise

    # Unpack the proven DTO directly into Tortoise
    return await UserDB.create(**dataclasses.asdict(safe_dto))
```