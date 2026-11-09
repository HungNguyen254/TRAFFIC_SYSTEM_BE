import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class Prediction(SQLModel, table=True):
    __tablename__ = "predictions"
    __table_args__ = (
        sa.UniqueConstraint("edge_id", "hour_of_day", name="uq_predictions_edge_hour"),
    )

    prediction_id: uuid.UUID = Field(
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
    hour_of_day: int = Field(
        sa_column=sa.Column(
            sa.Integer,
            sa.CheckConstraint("hour_of_day BETWEEN 0 AND 23"),
            nullable=False,
        )
    )
    predicted_speed: float
    risk_factor: float = Field(
        sa_column=sa.Column(
            sa.Float,
            sa.CheckConstraint("risk_factor BETWEEN 0 AND 1"),
            nullable=False,
        )
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
