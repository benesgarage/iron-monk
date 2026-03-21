# SQLAlchemy 2.0

SQLAlchemy 2.0 introduced the `MappedAsDataclass` mixin, which allows your ORM models to behave exactly like standard Python dataclasses. 

Because `iron-monk` relies on standard dataclass mechanics and pure Python type hints, you can decorate your SQLAlchemy models directly! This allows you to strictly validate your data *before* you ever commit it to the database, saving you from parsing ugly database `IntegrityError`s.

## The Integration

```python
from typing import Annotated
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass, Mapped, mapped_column

from monk import monk, validate
from monk.constraints import Email, Len
from monk.exceptions import ValidationError

# 1. Define the base class using the SQLAlchemy dataclass mixin
class Base(MappedAsDataclass, DeclarativeBase):
    pass

# 2. Decorate your ORM model with @monk!
@monk
class UserDB(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    
    # Wrap your Mapped types with Annotated constraints
    username: Mapped[Annotated[str, Len(min_len=3)]]
    email: Mapped[Annotated[str, Email]] = mapped_column(unique=True)

# 3. Instantiate your ORM model
new_user = UserDB(username="ab", email="bad-email")

# 4. Validate BEFORE adding to the session!
try:
    validate(new_user)
    # session.add(new_user)
    # session.commit()
except ValidationError as e:
    print("Database insert aborted! Validation failed:")
    print(e.flatten())
```

### Output
```bash
Database insert aborted! Validation failed:
['username: Must have a minimum length of 3.', 'email: Must be a valid email address.']
```