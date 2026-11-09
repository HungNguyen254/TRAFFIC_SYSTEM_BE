from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    chatbot,
    edges,
    nodes,
    predictions,
    routing,
    saved_places,
    search_histories,
    traffic_records,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth.router)
api_v1_router.include_router(nodes.router)
api_v1_router.include_router(edges.router)
api_v1_router.include_router(traffic_records.router)
api_v1_router.include_router(predictions.router)
api_v1_router.include_router(routing.router)
api_v1_router.include_router(saved_places.router)
api_v1_router.include_router(search_histories.router)
api_v1_router.include_router(chatbot.router)
api_v1_router.include_router(admin.router)
