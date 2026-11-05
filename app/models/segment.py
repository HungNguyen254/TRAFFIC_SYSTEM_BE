from typing import Optional
from sqlmodel import Field, SQLModel


class Segment(SQLModel, table=True):
    __tablename__ = "segment"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    length_m: float
    road_type: str
    free_flow_speed_kmh: float
