import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import check_db_connection, init_db
from app.core.response import StandardResponse, failed_response, success_response
from app.middlewares.middleware import setup_middleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        check_db_connection()
        init_db()
        logger.info("Successfully connected to Supabase PostgreSQL.")
    except (SQLAlchemyError, OSError) as exc:
        logger.error("Failed to connect to Supabase PostgreSQL: %s", exc)
    yield


app = FastAPI(title="Traffic System BE", version="0.1.2", lifespan=lifespan)

setup_middleware(app)


@app.get(
    "/api/data",
    response_model=StandardResponse[None],
    status_code=status.HTTP_200_OK,
    summary="API root",
    tags=["system"],
)
def root(request: Request):
    return success_response(
        request=request, message="Chào mừng đến với hệ thống dự báo tắc đường"
    )


@app.get(
    "/api/health",
    response_model=StandardResponse[dict[str, str]],
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": StandardResponse[None]}},
    summary="System health check",
    tags=["system"],
)
def health_check(request: Request, response: Response):
    db_status = "connected"
    try:
        check_db_connection()
    except (SQLAlchemyError, OSError) as exc:
        logger.warning("Health check: database unreachable: %s", exc)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return failed_response(
            request=request,
            message="Health check failed",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error="database unreachable",
        )

    return success_response(
        request=request,
        message="Health check passed",
        data={"status": "ok", "database": db_status},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG
    )
