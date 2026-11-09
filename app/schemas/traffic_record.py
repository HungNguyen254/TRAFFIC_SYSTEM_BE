import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TrafficRecordUpdate(BaseModel):
    edge_id: uuid.UUID
    current_speed: float = Field(ge=0)
    congestion_level: int | None = Field(default=None, ge=1, le=4)
    color_code: str | None = None


class TrafficRecordResponse(BaseModel):
    traffic_record_id: uuid.UUID
    edge_id: uuid.UUID
    current_speed: float
    congestion_level: int
    color_code: str
    updated_at: datetime
