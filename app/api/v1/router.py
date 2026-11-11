from fastapi import APIRouter

from app.api.v1.endpoints import (
    predictions,
    admin,
    auth,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(predictions.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(auth.router)