import io
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
