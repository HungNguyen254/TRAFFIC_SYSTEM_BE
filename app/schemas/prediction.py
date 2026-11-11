import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    edge_id: uuid.UUID | None = None
    street_name: str | None = None
    base_time: datetime | None = Field(
        default=None,
        description="Thời điểm bắt đầu dự báo (ISO-8601). Mặc định là thời điểm hiện tại.",
    )
    minutes_ahead: list[Annotated[int, Field(ge=1, le=1440)]] = Field(
        default=[30, 60, 120],
        min_length=1,
        description="Danh sách các mốc phút tương lai cần dự đoán (ví dụ: [30, 60, 120]).",
    )
    weather: str = Field(
        default="sunny",
        description="Điều kiện thời tiết (sunny, rain, heavy_rain...)",
    )


class PredictionTimelineItem(BaseModel):
    minutes_ahead: int
    target_time: datetime
    hour_of_day: int
    day_of_week: int
    predicted_speed: float
    max_speed_limit: int
    risk_factor: float
    congestion_level: int
    description: str


class PredictionResponse(BaseModel):
    edge_id: uuid.UUID
    street_name: str
    max_speed_limit: int
    base_time: datetime
    weather: str
    timeline: list[PredictionTimelineItem]
    updated_at: datetime
