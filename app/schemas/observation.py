from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


def ensure_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def serialize_utc_z(dt: datetime) -> str:
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat() + "Z"


class ObservationCreate(BaseModel):
    segment_id: int
    timestamp: datetime
    avg_speed_kmh: float
    vehicle_count: Optional[int] = None

    @field_validator("timestamp", mode="after")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        return ensure_naive_utc(v)


class ObservationRead(BaseModel):
    id: int
    segment_id: int
    timestamp: datetime
    avg_speed_kmh: float
    vehicle_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("timestamp")
    def serialize_timestamp(self, v: datetime) -> str:
        return serialize_utc_z(v)


class ObservationBulkResponse(BaseModel):
    inserted: int
    skipped: int
