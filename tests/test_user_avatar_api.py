import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.database import get_session
from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.api.v1.endpoints.auth import MAX_AVATAR_BYTES


@pytest.fixture
def engine():
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    return test_engine


@pytest.fixture
def db_session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(engine):
    def override_session():
        with Session(engine) as session:
            yield session

    original_override = app.dependency_overrides.get(get_session)
    app.dependency_overrides[get_session] = override_session
    try:
        yield TestClient(app)
    finally:
        if original_override is None:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = original_override


@pytest.fixture
def auth_headers(db_session):
    user = User(
        email="avatar-user@example.com",
        password_hash="not-used",
        full_name="Avatar User",
        role="user",
        token_version=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(
        {"sub": str(user.user_id), "token_version": user.token_version}
    )
    return {"Authorization": f"Bearer {token}"}


def test_avatar_upload_get_and_delete(client, auth_headers):
    image = b"\x89PNG\r\n\x1a\navatar-bytes"
    response = client.put(
        "/api/v1/auth/me/avatar",
        content=image,
        headers={**auth_headers, "Content-Type": "image/png"},
    )
    assert response.status_code == 200

    response = client.get("/api/v1/auth/me/avatar", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == image

    replacement = b"\xff\xd8\xffreplacement"
    response = client.put(
        "/api/v1/auth/me/avatar",
        content=replacement,
        headers={**auth_headers, "Content-Type": "image/jpeg"},
    )
    assert response.status_code == 200
    response = client.get("/api/v1/auth/me/avatar", headers=auth_headers)
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == replacement

    response = client.delete("/api/v1/auth/me/avatar", headers=auth_headers)
    assert response.status_code == 200
    assert client.get("/api/v1/auth/me/avatar", headers=auth_headers).status_code == 404


def test_avatar_upload_requires_authentication_and_valid_image(client):
    assert client.get("/api/v1/auth/me/avatar").status_code == 401
    response = client.put(
        "/api/v1/auth/me/avatar",
        content=b"not-an-image",
        headers={"Content-Type": "image/png"},
    )
    assert response.status_code == 401


def test_avatar_upload_rejects_mismatched_and_oversized_images(client, auth_headers):
    response = client.put(
        "/api/v1/auth/me/avatar",
        content=b"not-an-image",
        headers={**auth_headers, "Content-Type": "image/png"},
    )
    assert response.status_code == 415

    response = client.put(
        "/api/v1/auth/me/avatar",
        content=b"\x89PNG\r\n\x1a\n" + b"x" * MAX_AVATAR_BYTES,
        headers={**auth_headers, "Content-Type": "image/png"},
    )
    assert response.status_code == 413


def test_user_model_avatar_fields_default_to_none():
    user = User(
        email="test-defaults@example.com",
        password_hash="hash",
        full_name="Default User",
        role="user",
    )
    assert user.avatar_content_type is None
    assert user.avatar_data is None
    assert user.avatar_updated_at is None


def test_user_response_schema_has_avatar():
    from app.schemas.auth import UserResponse

    res = UserResponse(
        user_id=uuid.uuid4(),
        email="test@example.com",
        full_name="Test User",
        role="user",
        plan="standard",
        created_at=datetime.now(UTC),
        has_avatar=True,
    )
    assert res.has_avatar is True

