from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer

from app.schemas.observation import serialize_utc_z


class ForecastResponse(BaseModel):
    segment_id: int
    target_time: datetime
    predicted_speed_kmh: float
    congestion_level: str
    model_version: str = "baseline-v1"

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("target_time")
    def serialize_target_time(self, v: datetime) -> str:
        return serialize_utc_z(v)
