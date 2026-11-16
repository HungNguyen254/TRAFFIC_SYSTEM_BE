import io
from pathlib import Path
import joblib
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.ml_model import MLModel
from app.models.traffic_data import TrafficData
from scripts.train_prediction_model import train_model


def test_train_model_from_database_and_save_to_db():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Populate minimal records
        for i in range(20):
            session.add(
                TrafficData(
                    edge_code=f"EDGE_{i%4}",
                    street_name="Pho Hue",
                    length_km=1.5,
                    max_speed_limit=50,
                    hour_of_day=i % 24,
                    day_of_week=i % 7,
                    is_weekend=1 if (i % 7) in (5, 6) else 0,
                    is_rush_hour=1 if 7 <= (i % 24) <= 9 else 0,
                    weather_code=0.0,
                    average_speed=30.0 - (i % 10),
                    congestion_level=2,
                    risk_factor=0.4,
                )
            )
        session.commit()

        # Run training
        model, db_model = train_model(session=session)
        assert model is not None
        assert db_model is not None
        assert db_model.is_active is True
        assert db_model.version == 1

        # Check model can be loaded from model_bytes
        loaded_rf = joblib.load(io.BytesIO(db_model.model_bytes))
        assert loaded_rf is not None

        # Train second time: verify version increment and active deactivation
        model2, db_model2 = train_model(session=session)
        assert db_model2.version == 2
        assert db_model2.is_active is True

        old_model = session.exec(select(MLModel).where(MLModel.version == 1)).first()
        assert old_model.is_active is False


def test_train_model_auto_seeds_when_traffic_data_empty(monkeypatch, tmp_path: Path):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    # Point DEFAULT_CSV_PATH to sample csv with minimal valid rows
    dummy_csv = tmp_path / "synthetic_traffic_dataset.csv"
    with open(dummy_csv, "w", newline="", encoding="utf-8") as f:
        f.write(
            "edge_code,street_name,length_km,max_speed_limit,hour_of_day,day_of_week,is_weekend,is_rush_hour,weather_code,average_speed,congestion_level,risk_factor\n"
        )
        for i in range(15):
            f.write(f"EDGE_TEST,Street,1.0,50,{i%24},{i%7},0,0,0,30.0,2,0.4\n")

    monkeypatch.setattr("scripts.train_prediction_model.DEFAULT_CSV_PATH", dummy_csv)

    with Session(engine) as session:
        # Table is initially empty
        count = session.exec(select(TrafficData)).all()
        assert len(count) == 0

        model, db_model = train_model(session=session)
        assert model is not None
        assert db_model.is_active is True

        # Should have auto-seeded 15 records
        rows = session.exec(select(TrafficData)).all()
        assert len(rows) == 15
