import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from app.core.crypto import generate_salt


class User(SQLModel, table=True):
    __tablename__ = "users"

    user_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(sa.Uuid, primary_key=True, nullable=False),
    )
    email: str = Field(unique=True, index=True, max_length=100)
    password_hash: str = Field(max_length=255)
    full_name: str = Field(max_length=100)
    role: str = Field(default="user", max_length=20)
    # Gói người dùng: "standard" (mặc định) hoặc "premium"
    plan: str = Field(default="standard", max_length=20)
    plan_updated_at: datetime | None = Field(default=None, nullable=True)
    token_version: int = Field(default=1, nullable=False)
    encryption_salt: str = Field(default_factory=generate_salt, max_length=64, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
