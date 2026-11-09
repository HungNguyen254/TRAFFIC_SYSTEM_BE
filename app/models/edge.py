import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Edge(SQLModel, table=True):
    __tablename__ = "edges"

    edge_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    edge_code: str = Field(unique=True, index=True, max_length=20)
    street_name: str = Field(index=True, max_length=100)
    from_node_id: uuid.UUID = Field(foreign_key="nodes.node_id", index=True)
    to_node_id: uuid.UUID = Field(foreign_key="nodes.node_id", index=True)
    length_km: float
    max_speed_limit: int = Field(default=50)
    geom: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
