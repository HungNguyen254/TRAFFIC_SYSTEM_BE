import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SavedPlaceCreate(BaseModel):
    place_name: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=255)
    latitude: float
    longitude: float
    geom: str | None = None


class SavedPlaceResponse(BaseModel):
    saved_place_id: uuid.UUID
    user_id: uuid.UUID
    place_name: str
    address: str
    latitude: float
    longitude: float
    geom: str | None = None
    created_at: datetime
