from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings


def setup_middleware(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_headers=["*"],
        allow_methods=["*"],
        allow_origins=settings.ALLOWED_ORIGINS,
    )
    app.add_middleware(SlowAPIMiddleware)
