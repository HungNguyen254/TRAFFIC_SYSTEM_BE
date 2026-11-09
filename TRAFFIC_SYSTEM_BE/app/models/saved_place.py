from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Float, func
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import PlaceType

if TYPE_CHECKING:
    from app.models.user import User


class SavedPlace(SQLModel, table=True):
    """A location a user bookmarked (home, workplace, ...)."""

    __tablename__ = "saved_places"  # type: ignore[assignment]

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True, ondelete="CASCADE")

    name: str = Field(max_length=150, index=True)
    address: str | None = Field(default=None, max_length=500)

    latitude: float = Field(sa_type=Float, ge=-90.0, le=90.0)
    longitude: float = Field(sa_type=Float, ge=-180.0, le=180.0)

    place_type: PlaceType = Field(default=PlaceType.OTHER, index=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    user: "User" = Relationship(back_populates="saved_places")

    def __repr__(self) -> str:
        return (
            f"SavedPlace(id={self.id!r}, name={self.name!r}, "
            f"type={self.place_type!r})"
        )
