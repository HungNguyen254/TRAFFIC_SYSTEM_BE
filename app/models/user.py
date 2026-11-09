import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    user_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(sa.Uuid, primary_key=True, nullable=False),
    )
    email: str = Field(unique=True, index=True, max_length=100)
    password_hash: str = Field(max_length=255)
    full_name: str = Field(max_length=100)
    role: str = Field(
        default="user",
        sa_column=sa.Column(
            sa.String(20),
            sa.CheckConstraint("role IN ('user', 'admin')"),
            nullable=False,
        ),
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
