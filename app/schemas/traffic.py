import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NodeCreate(BaseModel):
    node_code: str = Field(min_length=1, max_length=20)
    node_name: str = Field(min_length=1, max_length=100)
    district: str = Field(min_length=1, max_length=50)
    latitude: float
    longitude: float
    geom: str | None = None


class NodeUpdate(BaseModel):
    node_code: str | None = None
    node_name: str | None = None
    district: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geom: str | None = None


class NodeResponse(BaseModel):
    node_id: uuid.UUID
    node_code: str
    node_name: str
    district: str
    latitude: float
    longitude: float
    geom: str | None = None
    created_at: datetime


class EdgeCreate(BaseModel):
    edge_code: str = Field(min_length=1, max_length=20)
    street_name: str = Field(min_length=1, max_length=100)
    from_node_id: uuid.UUID
    to_node_id: uuid.UUID
    length_km: float = Field(gt=0)
    max_speed_limit: int = Field(default=50, gt=0)
    geom: str | None = None


class EdgeUpdate(BaseModel):
    edge_code: str | None = None
    street_name: str | None = None
    from_node_id: uuid.UUID | None = None
    to_node_id: uuid.UUID | None = None
    length_km: float | None = None
    max_speed_limit: int | None = None
    geom: str | None = None


class EdgeResponse(BaseModel):
    edge_id: uuid.UUID
    edge_code: str
    street_name: str
    from_node_id: uuid.UUID
    to_node_id: uuid.UUID
    length_km: float
    max_speed_limit: int
    geom: str | None = None
    created_at: datetime
