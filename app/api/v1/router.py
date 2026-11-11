from fastapi import APIRouter

from app.api.v1.endpoints import (
    predictions
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(predictions.router)