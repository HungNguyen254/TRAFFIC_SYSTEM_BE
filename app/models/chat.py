import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_sessions"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(sa.Uuid, primary_key=True, nullable=False),
    )
    user_id: uuid.UUID = Field(
        sa_column=sa.Column(
            sa.Uuid,
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    title_encrypted: str | None = Field(default=None, nullable=True)
    title_nonce: str | None = Field(default=None, nullable=True)

    session_key_enc_user: str = Field(nullable=False)
    session_key_nonce_user: str = Field(nullable=False)
    session_key_enc_server: str = Field(nullable=False)
    session_key_nonce_server: str = Field(nullable=False)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(sa.Uuid, primary_key=True, nullable=False),
    )
    session_id: uuid.UUID = Field(
        sa_column=sa.Column(
            sa.Uuid,
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    role: str = Field(max_length=20, nullable=False)
    ciphertext: str = Field(nullable=False)
    nonce: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
