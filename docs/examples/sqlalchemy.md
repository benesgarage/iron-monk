# SQLAlchemy 2.0

Validate at the application boundary, then hand only proven data to SQLAlchemy. The DTO pattern below keeps validation rules out of your persistence layer and lets you reuse the same DTO across HTTP, queue, and CLI entry points.

Project: <https://github.com/sqlalchemy/sqlalchemy>

## The integration

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