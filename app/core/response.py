from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class StandardResponse[T](BaseModel):
    status_code: int
    message: str
    error: Any | None = None
    data: T | None = None
    path: str
    timestamp: Annotated[str, Field(default_factory=lambda: datetime.now(UTC).isoformat())]


def success_response[T](
    request: Request,
    message: str,
    status_code: int = status.HTTP_200_OK,
    data: T | None = None,
) -> StandardResponse[T]:
    return StandardResponse[T](
        status_code=status_code, message=message, data=data, path=request.url.path
    )


def error_response(
    request: Request,
    message: str,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    error: Any | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=StandardResponse[None](
            status_code=status_code, message=message, error=error, path=request.url.path
        ).model_dump(mode="json"),
    )
