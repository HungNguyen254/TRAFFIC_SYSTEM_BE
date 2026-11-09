import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class SearchHistory(SQLModel, table=True):
    __tablename__ = "search_histories"

    search_history_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    user_id: uuid.UUID | None = Field(default=None, foreign_key="users.user_id", index=True)
    origin_name: str = Field(max_length=150)
    origin_lat: float
    origin_lng: float
    destination_name: str = Field(max_length=150)
    destination_lat: float
    destination_lng: float
    searched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
