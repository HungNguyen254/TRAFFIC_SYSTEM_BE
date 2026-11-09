import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Prediction(SQLModel, table=True):
    __tablename__ = "predictions"

    prediction_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    edge_id: uuid.UUID = Field(foreign_key="edges.edge_id", index=True)
    hour_of_day: int = Field(ge=0, le=23)
    predicted_speed: float
    risk_factor: float
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
