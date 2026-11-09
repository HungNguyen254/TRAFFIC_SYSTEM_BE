import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.exceptions import AppException
from app.core.response import error_response

logger = logging.getLogger(__name__)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    logger.warning(
        "[AppException] %s | %s (code: %s)", request.url.path, exc.message, exc.error_code
    )
    return error_response(
        request=request,
        message=exc.message,
        status_code=exc.status_code,
        error=exc.error_code,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning("[HTTP %s] %s | %s", exc.status_code, request.url.path, exc.detail)
    return error_response(
        request=request,
        message=str(exc.detail) if isinstance(exc.detail, str) else "Lỗi yêu cầu HTTP",
        status_code=exc.status_code,
        error=exc.detail,
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.warning("[ValidationError] %s | %s", request.url.path, exc.errors())
    return error_response(
        request=request,
        message="Dữ liệu đầu vào không hợp lệ!",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error=exc.errors(),
    )


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    logger.warning("[ValueError] %s | %s", request.url.path, exc)
    return error_response(
        request=request,
        message="Dữ liệu không hợp lệ hoặc bị trùng!",
        status_code=status.HTTP_400_BAD_REQUEST,
        error="VALUE_ERROR",
    )


async def integrity_error_handler(
    request: Request, exc: IntegrityError
) -> JSONResponse:
    logger.error("[IntegrityError] %s | Detail: %s", request.url.path, exc.orig)
    return error_response(
        request=request,
        message="Lỗi vi phạm ràng buộc cơ sở dữ liệu!",
        status_code=status.HTTP_400_BAD_REQUEST,
        error="INTEGRITY_ERROR",
    )


async def sqlalchemy_error_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    logger.exception("[DatabaseError] %s | %s", request.url.path, exc)
    return error_response(
        request=request,
        message="Lỗi truy vấn cơ sở dữ liệu!",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error="DATABASE_ERROR",
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("[UnhandledError] %s | %s", request.url.path, exc)
    return error_response(
        request=request,
        message="Hệ thống gặp sự cố! Vui lòng thử lại sau!",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error="INTERNAL_SERVER_ERROR",
    )


def register_handler(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(ValueError, value_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
    app.add_exception_handler(Exception, general_exception_handler)

