# SQLAlchemy 2.0

> https://github.com/sqlalchemy/sqlalchemy

Validate your data at the edge of your application, and only pass proven, safe data to SQLAlchemy.

## The Integration

```python
from typing import Annotated
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from monk import monk, validate
from monk.constraints import Email, Len
from monk.exceptions import ValidationError

# 1. The Database Model (Pure Persistence)
class Base(DeclarativeBase):
    pass

class UserDB(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)

# 2. The DTO (Pure Validation)
@monk
class CreateUserDTO:
    username: Annotated[str, Len(min_len=3)]
    email: Annotated[str, Email]

# 3. The API / Service Handler
def register_user(payload: dict) -> UserDB:
    try:
        # Validate at the boundary
        safe_dto = validate(CreateUserDTO(**payload))
    except ValidationError as e:
        print("Request rejected:", e.flatten())
        raise
        
    # Hand pure data to the ORM
    new_user = UserDB(username=safe_dto.username, email=safe_dto.email)
    # session.add(new_user)
    # session.commit()
    return new_user
```