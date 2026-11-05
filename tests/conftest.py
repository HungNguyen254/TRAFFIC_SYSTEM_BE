import os
import tempfile
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_session


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    def get_session_override() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(name="auth_tokens")
def auth_tokens_fixture(session: Session) -> dict[str, dict[str, str]]:
    from app.core.security import create_access_token, hash_password
    from app.models.user import User, UserRole

    admin = User(
        username="fixture_admin",
        email="fixture_admin@test.com",
        hashed_password=hash_password("adminpass"),
        role=UserRole.ADMIN,
    )
    user = User(
        username="fixture_user",
        email="fixture_user@test.com",
        hashed_password=hash_password("userpass"),
        role=UserRole.USER,
    )
    session.add_all([admin, user])
    session.commit()
    session.refresh(admin)
    session.refresh(user)

    admin_token = create_access_token({"sub": str(admin.id), "role": admin.role, "username": admin.username})
    user_token = create_access_token({"sub": str(user.id), "role": user.role, "username": user.username})

    return {
        "admin": {"Authorization": f"Bearer {admin_token}"},
        "user": {"Authorization": f"Bearer {user_token}"},
    }


@pytest.fixture(scope="session", autouse=True)
def ensure_ml_model_available() -> None:
    """Ensure ml_forecaster has a model even in a fresh CI environment without pre-trained artifact."""
    from app.services.ml_forecaster import ml_forecaster
    if ml_forecaster._model is None:
        from sklearn.feature_extraction import DictVectorizer
        from sklearn.ensemble import HistGradientBoostingRegressor
        from sklearn.pipeline import Pipeline
        from app.services.features import FEATURE_COLUMNS

        dummy_row = {col: 1.0 for col in FEATURE_COLUMNS if col != "road_type"}
        dummy_row["road_type"] = "primary"
        dummy_pipe = Pipeline([
            ("vec", DictVectorizer(sparse=False)),
            ("reg", HistGradientBoostingRegressor(min_samples_leaf=1, max_iter=2, random_state=42)),
        ])
        dummy_pipe.fit([dummy_row, dummy_row], [30.0, 30.0])
        ml_forecaster._model = dummy_pipe

