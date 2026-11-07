from typing import Any


class AppException(Exception):
    def __init__(
        self,
        message: str = "Đã xảy ra lỗi trong hệ thống!",
        status_code: int = 400,
        error_code: str = "APP_ERROR",
        details: Any | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details
        super().__init__(message)


class NotFoundException(AppException):
    def __init__(
        self,
        message: str = "Không tìm thấy dữ liệu yêu cầu!",
        error_code: str = "NOT_FOUND",
        details: Any | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=404,
            error_code=error_code,
            details=details,
        )


class BadRequestException(AppException):
    def __init__(
        self,
        message: str = "Yêu cầu không hợp lệ!",
        error_code: str = "BAD_REQUEST",
        details: Any | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=400,
            error_code=error_code,
            details=details,
        )


class UnauthorizedException(AppException):
    def __init__(
        self,
        message: str = "Bạn chưa đăng nhập hoặc phiên làm việc đã hết hạn!",
        error_code: str = "UNAUTHORIZED",
        details: Any | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=401,
            error_code=error_code,
            details=details,
        )


class ForbiddenException(AppException):
    def __init__(
        self,
        message: str = "Bạn không có quyền thực hiện hành động này!",
        error_code: str = "FORBIDDEN",
        details: Any | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=403,
            error_code=error_code,
            details=details,
        )

