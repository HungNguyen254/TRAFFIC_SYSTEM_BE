import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class TrafficRecord(SQLModel, table=True):
    __tablename__ = "traffic_records"

    traffic_record_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(sa.Uuid, primary_key=True, nullable=False),
    )
    edge_id: uuid.UUID = Field(
        sa_column=sa.Column(
            sa.Uuid,
            sa.ForeignKey("edges.edge_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    current_speed: float
    congestion_level: int = Field(
        sa_column=sa.Column(
            sa.Integer,
            sa.CheckConstraint("congestion_level BETWEEN 1 AND 4"),
            nullable=False,
        )
    )
    color_code: str = Field(max_length=10)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
