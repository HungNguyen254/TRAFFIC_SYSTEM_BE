from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Request, status
from pydantic import BaseModel, Field


class StandardResponse[T](BaseModel):
    status_code: int
    message: str
    error: Any | None = None
    data: T | None = None
    path: str
    timestamp: Annotated[
        str, Field(default_factory=lambda: datetime.now(UTC).isoformat())
    ]


def success_response[T](
    request: Request,
    message: str,
    status_code: int = status.HTTP_200_OK,
    data: T | None = None,
) -> StandardResponse[T]:
    return StandardResponse[T](
        status_code=status_code, message=message, data=data, path=request.url.path
    )


def failed_response[T](
    request: Request,
    message: str,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    error: Any | None = None,
    data: T | None = None,
) -> StandardResponse[T]:
    return StandardResponse[T](
        status_code=status_code,
        message=message,
        error=error,
        data=data,
        path=request.url.path,
    )
