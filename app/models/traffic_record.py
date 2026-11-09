import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class TrafficRecord(SQLModel, table=True):
    __tablename__ = "traffic_records"

    traffic_record_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    edge_id: uuid.UUID = Field(foreign_key="edges.edge_id", index=True)
    current_speed: float
    congestion_level: int
    color_code: str = Field(max_length=10)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
