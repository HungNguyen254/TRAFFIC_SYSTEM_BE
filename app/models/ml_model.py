import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class MLModel(SQLModel, table=True):
    __tablename__ = "ml_models"

    model_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(sa.Uuid, primary_key=True, nullable=False),
    )
    model_name: str = Field(default="traffic_speed_rf", index=True, max_length=100)
    version: int = Field(default=1, index=True)
    model_bytes: bytes = Field(sa_column=sa.Column(sa.LargeBinary, nullable=False))
    metrics: dict[str, Any] | None = Field(default=None, sa_column=sa.Column(sa.JSON, nullable=True))
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
