from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class AuthService:
    @staticmethod
    def register_user(session: Session, payload: RegisterRequest) -> User:
        existing_user = session.exec(
            select(User).where(User.email == payload.email)
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email đã được đăng ký.",
            )

        user = User(
            email=str(payload.email),
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def authenticate_user(session: Session, payload: LoginRequest) -> TokenResponse:
        user = session.exec(
            select(User).where(User.email == payload.email)
        ).first()
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email hoặc mật khẩu không chính xác.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = create_access_token({"sub": str(user.user_id)})
        return TokenResponse(
            access_token=access_token,
            role=user.role,
            user_id=user.user_id,
        )
