import uuid
from datetime import datetime

from pydantic import BaseModel


class SearchHistoryResponse(BaseModel):
    search_history_id: uuid.UUID
    user_id: uuid.UUID | None
    origin_name: str
    origin_lat: float
    origin_lng: float
    destination_name: str
    destination_lat: float
    destination_lng: float
    searched_at: datetime


class DestinationCount(BaseModel):
    destination_name: str
    count: int


class SearchStatsResponse(BaseModel):
    total_searches: int
    top_destinations: list[DestinationCount]
