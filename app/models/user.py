import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    user_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    email: str = Field(unique=True, index=True, max_length=100)
    password_hash: str = Field(max_length=255)
    full_name: str = Field(max_length=100)
    role: str = Field(default="user", max_length=20)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
