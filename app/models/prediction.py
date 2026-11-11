import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

class Prediction(SQLModel, table=True):
    __tablename__ = "predictions"

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
    hour_of_day: int = Field(ge=0, le=23)
    predicted_speed: float
    risk_factor: float
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))