from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Float, func
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.user import User


class SearchHistory(SQLModel, table=True):
    """A route query the user performed (origin -> destination)."""

    __tablename__ = "search_histories"  # type: ignore[assignment]

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True, ondelete="CASCADE")

    # Origin
    origin_name: str | None = Field(default=None, max_length=255)
    origin_address: str | None = Field(default=None, max_length=500)
    origin_latitude: float = Field(sa_type=Float, ge=-90.0, le=90.0)
    origin_longitude: float = Field(sa_type=Float, ge=-180.0, le=180.0)

    # Destination
    destination_name: str | None = Field(default=None, max_length=255)
    destination_address: str | None = Field(default=None, max_length=500)
    destination_latitude: float = Field(sa_type=Float, ge=-90.0, le=90.0)
    destination_longitude: float = Field(sa_type=Float, ge=-180.0, le=180.0)

    distance_meters: float | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)

    searched_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), index=True
        ),
    )

    user: "User" = Relationship(back_populates="search_histories")

    def __repr__(self) -> str:
        return (
            f"SearchHistory(id={self.id!r}, "
            f"origin={self.origin_name!r}, destination={self.destination_name!r})"
        )
