from app.schemas.segment import SegmentCreate, SegmentRead
from app.schemas.observation import (
    ObservationCreate,
    ObservationRead,
    ObservationBulkResponse,
)
from app.schemas.traffic import CurrentTrafficRead
from app.schemas.forecast import ForecastResponse

__all__ = [
    "SegmentCreate",
    "SegmentRead",
    "ObservationCreate",
    "ObservationRead",
    "ObservationBulkResponse",
    "CurrentTrafficRead",
    "ForecastResponse",
]
