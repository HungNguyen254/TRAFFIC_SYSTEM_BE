from fastapi import APIRouter

from app.api.v1.endpoints import (
    directions,
    predictions,
    admin,
    auth,
    edges,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(predictions.router)
api_v1_router.include_router(directions.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(edges.router)