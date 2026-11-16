import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class TrafficData(SQLModel, table=True):
    __tablename__ = "traffic_data"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(sa.Uuid, primary_key=True, nullable=False),
    )
    edge_code: str = Field(index=True, max_length=50)
    street_name: str = Field(max_length=100)
    length_km: float
    max_speed_limit: int = Field(default=50)
    hour_of_day: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6)
    is_weekend: int = Field(ge=0, le=1)
    is_rush_hour: int = Field(ge=0, le=1)
    weather_code: float = Field(default=0.0)
    average_speed: float
    congestion_level: int = Field(ge=1, le=4)
    risk_factor: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
