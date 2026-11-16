import io
from unittest.mock import MagicMock
import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sqlmodel import Session, SQLModel, create_engine

from app.models.ml_model import MLModel
from app.services.prediction_service import PredictionService


def test_prediction_service_loads_active_model_from_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.prediction_service.engine", engine)

    # Train a dummy RF model
    rf = RandomForestRegressor(n_estimators=5, random_state=42)
    X = np.ones((10, 7), dtype=np.float32)
    y = np.ones((10,), dtype=np.float32) * 40.0
    rf.fit(X, y)

    buf = io.BytesIO()
    joblib.dump(rf, buf)
    model_bytes = buf.getvalue()

    with Session(engine) as session:
        entry = MLModel(
            model_name="traffic_speed_rf",
            version=1,
            model_bytes=model_bytes,
            is_active=True,
        )
        session.add(entry)
        session.commit()

        PredictionService.load_model(session=session)
        assert PredictionService._model is not None


def test_prediction_service_fallback_when_no_active_model(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.prediction_service.engine", engine)

    with Session(engine) as session:
        PredictionService.load_model(session=session)
        assert PredictionService._model is None


def test_prediction_service_corrupted_model_bytes_fallback(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.prediction_service.engine", engine)

    with Session(engine) as session:
        entry = MLModel(
            model_name="traffic_speed_rf",
            version=1,
            model_bytes=b"completely-corrupted-bytes-not-a-joblib-file",
            is_active=True,
        )
        session.add(entry)
        session.commit()

        # Should not raise exception, but fallback safely
        PredictionService.load_model(session=session)
        assert PredictionService._model is None


def test_prediction_service_reload_failure_retains_existing_model(monkeypatch):
    mock_model = MagicMock()
    PredictionService._model = mock_model

    # Simulate DB error during reload
    failing_session = MagicMock()
    failing_session.exec.side_effect = RuntimeError("Database connection timed out")

    PredictionService.load_model(session=failing_session)
    # The existing model should be preserved rather than wiped
    assert PredictionService._model is mock_model
