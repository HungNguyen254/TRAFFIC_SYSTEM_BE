from sqlmodel import Session, SQLModel, create_engine, select

from app.api.v1.endpoints.admin import _run_retraining
from app.models.ml_model import MLModel
from app.models.traffic_data import TrafficData
from app.services.prediction_service import PredictionService


def test_admin_retrain_flow(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.core.database.engine", engine)
    monkeypatch.setattr("scripts.train_prediction_model.engine", engine)
    monkeypatch.setattr("app.services.prediction_service.engine", engine)

    # Seed some traffic data
    with Session(engine) as session:
        for i in range(15):
            session.add(
                TrafficData(
                    edge_code="EDGE_TEST",
                    street_name="Test St",
                    length_km=1.0,
                    max_speed_limit=50,
                    hour_of_day=8,
                    day_of_week=0,
                    is_weekend=0,
                    is_rush_hour=1,
                    weather_code=0.0,
                    average_speed=30.0,
                    congestion_level=2,
                    risk_factor=0.4,
                )
            )
        session.commit()

    _run_retraining()

    assert PredictionService._model is not None
    with Session(engine) as session:
        active = session.exec(select(MLModel).where(MLModel.is_active == True)).first()
        assert active is not None
        assert active.version >= 1
