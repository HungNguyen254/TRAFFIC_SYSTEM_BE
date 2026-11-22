from typing import Annotated
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.database import SessionDep
from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpgradePlanResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


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
    )
    return success_response(request=request, message="Lấy thông tin thành công", data=user_res)


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
