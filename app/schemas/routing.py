import uuid
from typing import Literal

from pydantic import BaseModel

SpeedSource = Literal["predicted", "limit"]
WeightMode = Literal["distance", "duration"]


class RouteStep(BaseModel):
    edge_id: uuid.UUID
    edge_code: str
    street_name: str
    length_km: float
    travel_min: float
    speed_kmh: float
    risk_factor: float
    speed_source: SpeedSource


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
    max_risk_factor: float
    hour_of_day: int | None
