import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class UserAvatar(SQLModel, table=True):
    __tablename__ = "user_avatars"

    user_id: uuid.UUID = Field(
        sa_column=sa.Column(
            sa.Uuid,
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        )
    )
    content_type: str = Field(max_length=32)
    image_data: bytes = Field(
        sa_column=sa.Column(sa.LargeBinary, nullable=False),
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
