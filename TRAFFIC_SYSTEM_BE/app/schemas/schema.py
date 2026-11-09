"""All Pydantic request/response schemas for the API.

Input models are plain ``BaseModel``; ``*Read`` models opt into
``from_attributes=True`` so they can be built straight from ORM objects.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import PlaceType, UserRole

# --------------------------------------------------------------------------- #
# User
# --------------------------------------------------------------------------- #


class UserBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr = Field(max_length=255)


class UserRegister(UserBase):
    """Payload sent by the client when signing up (cannot pick its role)."""

    password: str = Field(min_length=8, max_length=128)


class UserCreate(UserBase):
    """Payload used by admin/internal code to create an account."""

    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.USER
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: UserRole | None = None
    is_active: bool | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


# --------------------------------------------------------------------------- #
# SavedPlace
# --------------------------------------------------------------------------- #


class SavedPlaceBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    address: str | None = Field(default=None, max_length=500)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    place_type: PlaceType = PlaceType.OTHER


class SavedPlaceCreate(SavedPlaceBase):
    pass


class SavedPlaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    address: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    place_type: PlaceType | None = None


class SavedPlaceRead(SavedPlaceBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    created_at: datetime


# --------------------------------------------------------------------------- #
# SearchHistory
# --------------------------------------------------------------------------- #


class CoordinatePoint(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)


class SearchHistoryCreate(BaseModel):
    origin: CoordinatePoint
    destination: CoordinatePoint
    distance_meters: float | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)


class SearchHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID

    origin_name: str | None
    origin_address: str | None
    origin_latitude: float
    origin_longitude: float

    destination_name: str | None
    destination_address: str | None
    destination_latitude: float
    destination_longitude: float

    distance_meters: float | None
    duration_seconds: int | None
    searched_at: datetime
