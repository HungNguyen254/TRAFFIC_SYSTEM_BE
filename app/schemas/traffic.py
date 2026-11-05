from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_serializer
from app.schemas.observation import serialize_utc_z


class CurrentTrafficRead(BaseModel):
    segment_id: int
    timestamp: datetime
    avg_speed_kmh: float
    vehicle_count: Optional[int] = None
    congestion_level: str

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("timestamp")
    def serialize_timestamp(self, v: datetime) -> str:
        return serialize_utc_z(v)
