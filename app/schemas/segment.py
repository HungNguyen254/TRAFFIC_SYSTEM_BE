from typing import Optional
from pydantic import BaseModel, ConfigDict


class SegmentBase(BaseModel):
    name: str
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    length_m: float
    road_type: str
    free_flow_speed_kmh: float


class SegmentCreate(SegmentBase):
    pass


class SegmentUpdate(BaseModel):
    name: Optional[str] = None
    start_lat: Optional[float] = None
    start_lng: Optional[float] = None
    end_lat: Optional[float] = None
    end_lng: Optional[float] = None
    length_m: Optional[float] = None
    road_type: Optional[str] = None
    free_flow_speed_kmh: Optional[float] = None


class SegmentRead(SegmentBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
