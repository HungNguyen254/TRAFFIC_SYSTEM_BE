import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class SavedPlace(SQLModel, table=True):
    __tablename__ = "saved_places"

    saved_place_id: uuid.UUID = Field(
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
    place_name: str = Field(max_length=100)
    address: str = Field(max_length=255)
    latitude: float
    longitude: float
    geom: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
