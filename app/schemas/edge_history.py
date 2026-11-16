import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class EdgeHourlyBucket(BaseModel):
    time: datetime
    hour_of_day: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6, description="0 = thứ 2 ... 6 = chủ nhật")
    is_rush_hour: int = Field(ge=0, le=1)
    average_speed: float | None = None
    min_speed: float | None = None
    max_speed: float | None = None
    congestion_level: int | None = Field(
        default=None, ge=1, le=4, description="Suy ra từ average_speed, khớp legend bản đồ"
    )
    congestion_text: str | None = None
    risk_factor: float | None = None
    sample_count: int = Field(ge=0)


class EdgeHourlyHistoryResponse(BaseModel):
    edge_id: uuid.UUID
    edge_code: str
    street_name: str
    length_km: float
    max_speed_limit: int
    start: datetime
    end: datetime
    granularity: str
    timezone: str
    data_source: str
    total_hours: int
    hours_with_data: int
    buckets: list[EdgeHourlyBucket]
