from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.forecast import router as forecast_router
from app.api.observations import router as observations_router
from app.api.segments import router as segments_router
from app.api.traffic import router as traffic_router
from app.core.config import settings

app = FastAPI(title="Traffic Congestion Forecasting API", version="1.0.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


# Register API routers with /api prefix
app.include_router(segments_router, prefix="/api")
app.include_router(observations_router, prefix="/api")
app.include_router(traffic_router, prefix="/api")
app.include_router(forecast_router, prefix="/api")
app.include_router(auth_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="[IP_ADDRESS]", port=8000, reload=True)
