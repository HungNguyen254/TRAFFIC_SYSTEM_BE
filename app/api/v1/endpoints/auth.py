from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.database import SessionDep
from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth import (
    AvatarUploadResponse,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpgradePlanResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_AVATAR_BYTES = 2 * 1024 * 1024
AVATAR_SIGNATURES = {
    "image/png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "image/webp": lambda data: (
        len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    ),
}


def require_premium(user: User) -> None:
    """Kiểm tra quyền truy cập tính năng Premium."""
    if user.plan != "premium":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tính năng này chỉ dành cho tài khoản Premium. Vui lòng nâng cấp gói để sử dụng.",
        )


@router.post(
    "/register",
    response_model=StandardResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Đăng ký tài khoản người dùng / admin",
)
@limiter.limit("5/minute")
def register(request: Request, payload: RegisterRequest, session: SessionDep):
    user = AuthService.register_user(session, payload)
    user_res = UserResponse(
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        plan=user.plan,
        created_at=user.created_at,
        has_avatar=bool(user.avatar_data),
    )
    return success_response(request=request, message="Đăng ký tài khoản thành công", data=user_res)


@router.post(
    "/login",
    response_model=StandardResponse[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Đăng nhập nhận Access Token",
)
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, session: SessionDep):
    token_res = AuthService.authenticate_user(session, payload)
    return success_response(request=request, message="Đăng nhập thành công", data=token_res)


@router.get(
    "/me",
    response_model=StandardResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Lấy thông tin tài khoản đang đăng nhập",
)
def get_me(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
    user_res = UserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        plan=current_user.plan,
        created_at=current_user.created_at,
        has_avatar=bool(current_user.avatar_data),
    )
    return success_response(request=request, message="Lấy thông tin thành công", data=user_res)


@router.get(
    "/me/avatar",
    status_code=status.HTTP_200_OK,
    summary="Lấy ảnh đại diện tài khoản",
)
def get_my_avatar(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if not current_user.avatar_data or not current_user.avatar_content_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tài khoản chưa có ảnh đại diện.",
        )
    return Response(
        content=current_user.avatar_data,
        media_type=current_user.avatar_content_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.put(
    "/me/avatar",
    response_model=StandardResponse[AvatarUploadResponse],
    status_code=status.HTTP_200_OK,
    summary="Tải ảnh đại diện tài khoản",
)
async def upload_my_avatar(
    request: Request,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    signature_check = AVATAR_SIGNATURES.get(content_type)
    if not signature_check:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Chỉ hỗ trợ ảnh PNG, JPEG hoặc WebP.",
        )

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_AVATAR_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Ảnh đại diện không được vượt quá 2 MB.",
                )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kích thước ảnh tải lên không hợp lệ.",
            ) from exc

    image_data = bytearray()
    async for chunk in request.stream():
        if len(image_data) + len(chunk) > MAX_AVATAR_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Ảnh đại diện không được vượt quá 2 MB.",
            )
        image_data.extend(chunk)

    if not image_data or not signature_check(image_data):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Tệp tải lên không khớp định dạng ảnh đã chọn.",
        )

    current_user.avatar_content_type = content_type
    current_user.avatar_data = bytes(image_data)
    current_user.avatar_updated_at = datetime.now(UTC)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    return success_response(
        request=request,
        message="Cập nhật ảnh đại diện thành công.",
        data=AvatarUploadResponse(content_type=content_type),
    )


@router.delete(
    "/me/avatar",
    response_model=StandardResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Xóa ảnh đại diện tài khoản",
)
def delete_my_avatar(
    request: Request,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.avatar_data is not None:
        current_user.avatar_content_type = None
        current_user.avatar_data = None
        current_user.avatar_updated_at = None
        session.add(current_user)
        session.commit()
        session.refresh(current_user)
    return success_response(
        request=request,
        message="Đã xóa ảnh đại diện.",
        data=None,
    )


@router.post(
    "/upgrade-plan",
    response_model=StandardResponse[UpgradePlanResponse],
    status_code=status.HTTP_200_OK,
    summary="Nâng cấp tài khoản lên gói Premium (chưa tích hợp cổng thanh toán)",
)
def upgrade_plan(
    request: Request,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Tự động nâng cấp lên Premium khi người dùng chọn gói (demo, chưa cần thanh toán)."""
    if current_user.plan != "premium":
        current_user.plan = "premium"
        current_user.plan_updated_at = datetime.now(UTC)
        session.add(current_user)
        session.commit()
        session.refresh(current_user)

    return success_response(
        request=request,
        message="Nâng cấp gói Premium thành công",
        data=UpgradePlanResponse(
            user_id=current_user.user_id,
            plan=current_user.plan,
            message="Tài khoản của bạn đã được nâng cấp lên Premium.",
        ),
    )


@router.post(
    "/cancel-premium",
    response_model=StandardResponse[UpgradePlanResponse],
    status_code=status.HTTP_200_OK,
    summary="Hủy gói Premium, quay về Standard",
)
def cancel_premium(
    request: Request,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Hủy gói Premium của tài khoản đang đăng nhập (demo, chưa tích hợp cổng thanh toán)."""
    if current_user.plan != "standard":
        current_user.plan = "standard"
        current_user.plan_updated_at = datetime.now(UTC)
        session.add(current_user)
        session.commit()
        session.refresh(current_user)

    return success_response(
        request=request,
        message="Hủy gói Premium thành công",
        data=UpgradePlanResponse(
            user_id=current_user.user_id,
            plan=current_user.plan,
            message="Tài khoản của bạn đã quay về gói Standard.",
        ),
    )


@router.post(
    "/change-password",
    response_model=StandardResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Đổi mật khẩu tài khoản đang đăng nhập",
)
@limiter.limit("5/minute")
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    AuthService.change_password(session, current_user, payload)
    return success_response(request=request, message="Đổi mật khẩu thành công")
