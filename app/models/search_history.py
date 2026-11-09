import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class SearchHistory(SQLModel, table=True):
    __tablename__ = "search_histories"

    search_history_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(sa.Uuid, primary_key=True, nullable=False),
    )
    user_id: uuid.UUID | None = Field(
        default=None,
        sa_column=sa.Column(
            sa.Uuid,
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
    )
    origin_name: str = Field(max_length=150)
    origin_lat: float
    origin_lng: float
    destination_name: str = Field(max_length=150)
    destination_lat: float
    destination_lng: float
    searched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
