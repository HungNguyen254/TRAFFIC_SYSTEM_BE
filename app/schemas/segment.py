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
    name: str | None = None
    start_lat: float | None = None
    start_lng: float | None = None
    end_lat: float | None = None
    end_lng: float | None = None
    length_m: float | None = None
    road_type: str | None = None
    free_flow_speed_kmh: float | None = None


class SegmentRead(SegmentBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
