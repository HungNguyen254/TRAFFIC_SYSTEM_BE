import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlmodel import select

from app.core.config import settings
from app.core.database import SessionDep
from app.models.user import User

password_hash = PasswordHash((Argon2Hasher(),))
security_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def get_optional_user(
    auth: Annotated[HTTPAuthorizationCredentials | None, Depends(security_bearer)],
    session: SessionDep,
) -> User | None:
    if not auth or not auth.credentials:
        return None
    payload = decode_access_token(auth.credentials)
    if not payload or "sub" not in payload:
        return None
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError:
        return None
    user = session.exec(select(User).where(User.user_id == user_id)).first()
    if not user:
        return None
    token_version = payload.get("token_version")
    if token_version is None or token_version != user.token_version:
        return None
    return user


def get_current_user(
    auth: Annotated[HTTPAuthorizationCredentials | None, Depends(security_bearer)],
    session: SessionDep,
) -> User:
    user = get_optional_user(auth, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản chưa được xác thực hoặc phiên đăng nhập đã hết hạn.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ có Quản trị viên (Admin) mới có quyền thực hiện thao tác này.",
        )
    return current_user
