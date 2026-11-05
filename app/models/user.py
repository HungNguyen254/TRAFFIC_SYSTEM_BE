from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    USER = "USER"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    role: UserRole = Field(default=UserRole.USER)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        sa_type=sa.DateTime,
    )
