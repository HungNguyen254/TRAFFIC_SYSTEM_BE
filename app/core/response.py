from fastapi import Request, status
from pydantic import BaseModel, Field
from typing import Annotated, Any

from datetime import datetime, UTC


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
