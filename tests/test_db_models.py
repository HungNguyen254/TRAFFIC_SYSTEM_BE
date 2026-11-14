import uuid
from datetime import UTC, datetime
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.ml_model import MLModel
from app.models.traffic_data import TrafficData


def test_traffic_data_model_and_table():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        record = TrafficData(
            edge_code="EDGE_01",
            street_name="Pho Hue",
            length_km=1.2,
            max_speed_limit=50,
            hour_of_day=8,
            day_of_week=1,
            is_weekend=0,
            is_rush_hour=1,
            weather_code=0.0,
            average_speed=22.5,
            congestion_level=2,
            risk_factor=0.55,
        )
        session.add(record)
        session.commit()

        queried = session.exec(select(TrafficData).where(TrafficData.edge_code == "EDGE_01")).first()
        assert queried is not None
        assert queried.average_speed == 22.5
        assert isinstance(queried.id, uuid.UUID)


def test_ml_model_storage_and_query():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        fake_bytes = b"fake-model-binary-data"
        model_entry = MLModel(
            model_name="traffic_speed_rf",
            version=1,
            model_bytes=fake_bytes,
            metrics={"r2": 0.85},
            is_active=True,
        )
        session.add(model_entry)
        session.commit()

        active_model = session.exec(
            select(MLModel).where(MLModel.model_name == "traffic_speed_rf", MLModel.is_active == True)
        ).first()
        assert active_model is not None
        assert active_model.model_bytes == fake_bytes
        assert active_model.version == 1
