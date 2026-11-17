import uuid
from typing import Literal

from pydantic import BaseModel

WeightMode = Literal["distance", "duration"]
SpeedSource = Literal["limit", "current", "forecast"]


class RouteStep(BaseModel):
    edge_id: uuid.UUID
    edge_code: str
    street_name: str
    length_km: float
    travel_min: float
    speed_kmh: float
    congestion_level: int | None = None


class RouteResult(BaseModel):
    origin_node_id: uuid.UUID
    destination_node_id: uuid.UUID
    node_ids: list[uuid.UUID]
    node_names: list[str]
    edge_ids: list[uuid.UUID]
    steps: list[RouteStep]
    polyline: list[list[float]]
    total_distance_km: float
    total_duration_min: float


class RouteOption(BaseModel):
    route: RouteResult
    congestion_level: float
    at_risk: bool


class AlternativesResult(BaseModel):
    origin_node_id: uuid.UUID
    destination_node_id: uuid.UUID
    main_route_at_risk: bool
    has_alternative: bool
    options: list[RouteOption]
    message: str
