import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Node(SQLModel, table=True):
    __tablename__ = "nodes"

    node_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    node_code: str = Field(unique=True, index=True, max_length=20)
    node_name: str = Field(index=True, max_length=100)
    district: str = Field(max_length=50)
    latitude: float
    longitude: float
    geom: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
