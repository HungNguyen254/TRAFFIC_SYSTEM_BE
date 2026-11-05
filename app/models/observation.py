from datetime import datetime
from typing import Optional
import sqlalchemy as sa
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class TrafficObservation(SQLModel, table=True):
    __tablename__ = "trafficobservation"
    __table_args__ = (
        UniqueConstraint("segment_id", "timestamp", name="uq_segment_timestamp"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    segment_id: int = Field(foreign_key="segment.id", index=True)
    timestamp: datetime = Field(index=True, sa_type=sa.DateTime)
    avg_speed_kmh: float
    vehicle_count: Optional[int] = Field(default=None)
