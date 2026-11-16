import uuid
from unittest.mock import MagicMock
import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.core.security import (
    create_access_token,
    decode_access_token,
    get_optional_user,
    hash_password,
)
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest
from app.services.auth_service import AuthService


def test_password_change_increments_token_version_and_invalidates_old_token():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            user_id=uuid.uuid4(),
            email="victim@example.com",
            password_hash=hash_password("OldPassword123!"),
            full_name="Victim User",
            token_version=1,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        # Authenticate user to get initial token
        token_resp = AuthService.authenticate_user(
            session, LoginRequest(email="victim@example.com", password="OldPassword123!")
        )
        old_token = token_resp.access_token

        # Verify old token works
        mock_auth = MagicMock(credentials=old_token)
        resolved = get_optional_user(mock_auth, session)
        assert resolved is not None
        assert resolved.user_id == user.user_id

        # User changes password
        AuthService.change_password(
            session,
            user,
            ChangePasswordRequest(
                current_password="OldPassword123!",
                new_password="NewSecurePassword456!",
            ),
        )
        session.refresh(user)

        # Token version must have been incremented
        assert user.token_version == 2

        # Old token must now be completely revoked
        resolved_after = get_optional_user(mock_auth, session)
        assert resolved_after is None

        # Authenticating with new password produces a valid token
        new_token_resp = AuthService.authenticate_user(
            session, LoginRequest(email="victim@example.com", password="NewSecurePassword456!")
        )
        mock_auth_new = MagicMock(credentials=new_token_resp.access_token)
        resolved_new = get_optional_user(mock_auth_new, session)
        assert resolved_new is not None
        assert resolved_new.user_id == user.user_id


def test_token_without_token_version_is_rejected():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            user_id=uuid.uuid4(),
            email="test@example.com",
            password_hash=hash_password("Pass123!"),
            full_name="Test",
            token_version=1,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        # Token created without token_version in claims
        legacy_token = create_access_token({"sub": str(user.user_id), "role": user.role})
        mock_auth = MagicMock(credentials=legacy_token)
        resolved = get_optional_user(mock_auth, session)
        assert resolved is None
