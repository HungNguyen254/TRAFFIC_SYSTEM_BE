from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.saved_place import SavedPlace
    from app.models.search_history import SearchHistory


class User(SQLModel, table=True):
    __tablename__ = "users"  # type: ignore[assignment]

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    full_name: str = Field(max_length=150, index=True)
    email: str = Field(max_length=255, unique=True, index=True)
    password_hash: str = Field(max_length=255)
    role: UserRole = Field(default=UserRole.USER, index=True)
    is_active: bool = Field(default=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=True,
        ),
    )

    saved_places: list["SavedPlace"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    search_histories: list["SearchHistory"] = Relationship(
        back_populates="user", cascade_delete=True
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r}, role={self.role!r})"
