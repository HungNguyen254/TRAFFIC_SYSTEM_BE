import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NodeBrief(BaseModel):
    node_code: str
    node_name: str
    district: str | None = None
    lat: float
    lng: float


class EdgeStatusItem(BaseModel):
    edge_id: uuid.UUID
    edge_code: str
    street_name: str
    length_km: float
    max_speed_limit: int
    from_node: NodeBrief | None = None
    to_node: NodeBrief | None = None
    speed: float
    congestion_level: int = Field(
        ge=1, le=4, description="1: Thông thoáng, 2: Di chuyển chậm, 3: Ùn tắc nghiêm trọng, 4: Kẹt xe hoàn toàn"
    )
    congestion_text: str
    updated_at: datetime


class EdgeStatusResponse(BaseModel):
    total: int
    updated_at: datetime
    filters: dict[str, Any] = Field(default_factory=dict)
    edges: list[EdgeStatusItem]
