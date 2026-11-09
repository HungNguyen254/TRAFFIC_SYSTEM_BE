import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class SavedPlace(SQLModel, table=True):
    __tablename__ = "saved_places"

    saved_place_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    user_id: uuid.UUID = Field(foreign_key="users.user_id", index=True)
    place_name: str = Field(max_length=100)
    address: str = Field(max_length=255)
    latitude: float
    longitude: float
    geom: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
