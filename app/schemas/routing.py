import uuid

from pydantic import BaseModel, Field

from app.schemas.traffic import NodeResponse


class RouteRequest(BaseModel):
    origin_id: uuid.UUID | None = None
    origin_name: str | None = None
    destination_id: uuid.UUID | None = None
    destination_name: str | None = None
    hour_of_day: int = Field(default=8, ge=0, le=23)
    day_of_week: int = Field(default=0, ge=0, le=6)
    weather: str = Field(default="sunny")


class RouteSegmentDetail(BaseModel):
    edge_id: uuid.UUID
    street_name: str
    length_km: float
    predicted_speed: float
    risk_factor: float
    congestion_level: int


class RouteResponse(BaseModel):
    origin: NodeResponse
    destination: NodeResponse
    nodes: list[NodeResponse]
    segments: list[RouteSegmentDetail]
    total_distance_km: float
    estimated_time_minutes: float
    congestion_warning: str | None = None
