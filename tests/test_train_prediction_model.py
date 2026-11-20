import io
from pathlib import Path
import joblib
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.ml_model import MLModel
from app.models.traffic_data import TrafficData
from scripts.train_prediction_model import evaluate_and_compare_models, train_model
import numpy as np


def test_evaluate_and_compare_models():
    # Generate simple regression dataset where target has non-linear and linear relationships
    np.random.seed(42)
    X = np.random.uniform(1.0, 10.0, size=(100, 7)).astype(np.float32)
    # y depends strongly on features with small noise
    y = (2.0 * X[:, 0] + 0.5 * (X[:, 1] ** 2) + np.random.normal(0, 0.5, size=100)).astype(np.float32)

    results = evaluate_and_compare_models(X, y, test_size=0.2, random_state=42)

    assert "baseline" in results
    assert "linear_regression" in results
    assert "random_forest" in results

    assert "mae" in results["baseline"]
    assert "mae" in results["linear_regression"]
    assert "mae" in results["random_forest"]

    # Random forest or linear regression should have lower MAE than mean baseline
    assert results["random_forest"]["mae"] < results["baseline"]["mae"]
    assert "rmse" in results["random_forest"]
    assert "r2" in results["random_forest"]


def test_train_model_saves_file_and_evaluates_metrics(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    save_path = tmp_path / "models" / "traffic_model.joblib"

    with Session(engine) as session:
        for i in range(25):
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

        model, db_model, metrics = train_model(session=session, save_file_path=save_path)
        assert model is not None
        assert db_model is not None
        assert db_model.is_active is True
        assert save_path.exists()

        # Verify joblib file load
        loaded_model = joblib.load(save_path)
        sample_input = np.array([[12.0, 2.0, 0.0, 0.0, 0.0, 1.5, 50.0]], dtype=np.float32)
        pred = loaded_model.predict(sample_input)
        assert len(pred) == 1
        assert pred[0] > 0

        # Verify metrics recorded in DB
        assert "mae" in db_model.metrics
        assert "baseline_mae" in db_model.metrics
        assert db_model.metrics["mae"] == metrics["random_forest"]["mae"]


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
        model, db_model, *rest = train_model(session=session)
        assert model is not None
        assert db_model is not None
        assert db_model.is_active is True
        assert db_model.version == 1

        # Check model can be loaded from model_bytes
        loaded_rf = joblib.load(io.BytesIO(db_model.model_bytes))
        assert loaded_rf is not None

        # Train second time: verify version increment and active deactivation
        model2, db_model2, *rest = train_model(session=session)
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

        model, db_model, *rest = train_model(session=session)
        assert model is not None
        assert db_model.is_active is True

        # Should have auto-seeded 15 records
        rows = session.exec(select(TrafficData)).all()
        assert len(rows) == 15
