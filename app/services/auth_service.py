from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)


class AuthService:
    @staticmethod
    def register_user(session: Session, payload: RegisterRequest) -> User:
        existing = session.exec(select(User).where(User.email == payload.email)).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email này đã được đăng ký trong hệ thống.",
            )

        user = User(
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def authenticate_user(session: Session, payload: LoginRequest) -> TokenResponse:
        user = session.exec(select(User).where(User.email == payload.email)).first()
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email hoặc mật khẩu không chính xác.",
            )

        token = create_access_token(data={"sub": str(user.user_id), "role": user.role})
        return TokenResponse(
            access_token=token,
            role=user.role,
            user_id=user.user_id,
        )

    @staticmethod
    def change_password(
        session: Session, user: User, payload: ChangePasswordRequest
    ) -> None:
        if not verify_password(payload.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu hiện tại không chính xác.",
            )

        user.password_hash = hash_password(payload.new_password)
        session.add(user)
        session.commit()
