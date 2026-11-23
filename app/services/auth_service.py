from fastapi import HTTPException, status
from sqlalchemy import func
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
        normalized_email = payload.email.strip().lower()
        existing = session.exec(select(User).where(func.lower(User.email) == normalized_email)).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email này đã được đăng ký trong hệ thống.",
            )

        user = User(
            email=normalized_email,
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
        normalized_email = payload.email.strip().lower()
        user = session.exec(select(User).where(func.lower(User.email) == normalized_email)).first()
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email hoặc mật khẩu không chính xác.",
            )

        token = create_access_token(
            data={"sub": str(user.user_id), "role": user.role, "token_version": user.token_version}
        )
        return TokenResponse(
            access_token=token,
            role=user.role,
            plan=user.plan,
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

        # Re-wrap user chat session keys using the new password's derived User Master Key
        from app.core.crypto import (
            decrypt_server_secret,
            derive_user_master_key,
            encrypt_aes_gcm,
        )
        from app.models.chat import ChatSession

        if user.encryption_salt:
            new_user_mk = derive_user_master_key(payload.new_password, user.encryption_salt)
            chat_sessions = session.exec(
                select(ChatSession).where(ChatSession.user_id == user.user_id)
            ).all()
            for cs in chat_sessions:
                try:
                    k_session = decrypt_server_secret(
                        cs.session_key_enc_server,
                        cs.session_key_nonce_server,
                    )
                    enc_user, nonce_user = encrypt_aes_gcm(new_user_mk, k_session)
                    cs.session_key_enc_user = enc_user
                    cs.session_key_nonce_user = nonce_user
                    session.add(cs)
                except Exception:
                    pass

        user.password_hash = hash_password(payload.new_password)
        user.token_version += 1
        session.add(user)
        session.commit()
