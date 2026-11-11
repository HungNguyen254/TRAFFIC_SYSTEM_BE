from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.database import SessionDep
from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


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
        created_at=current_user.created_at,
    )
    return success_response(request=request, message="Lấy thông tin thành công", data=user_res)
