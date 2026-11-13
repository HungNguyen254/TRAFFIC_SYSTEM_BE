"""Train Traffic Congestion Machine Learning Model using data from database and persist model to database."""

import io
import logging
import sys
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sqlalchemy import func, update
from sqlmodel import Session, select

from app.core.database import engine, init_db
from app.models.ml_model import MLModel
from app.models.traffic_data import TrafficData

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "traffic_speed_rf"
DEFAULT_CSV_PATH = Path("data/synthetic_traffic_dataset.csv")


def train_model(
    session: Session | None = None,
    model_name: str = DEFAULT_MODEL_NAME,
) -> tuple[RandomForestRegressor, MLModel]:
    init_db()

    owns_session = session is None
    if owns_session:
        db_session = Session(engine)
    else:
        db_session = session

    try:
        # Check if traffic_data has records
        count_stmt = select(func.count(TrafficData.id))
        total_records = db_session.exec(count_stmt).one()

        if total_records == 0:
            logger.info("No traffic data found in database. Attempting to seed from CSV/generator...")
            if not DEFAULT_CSV_PATH.exists():
                from scripts.generate_synthetic_traffic import generate_dataset

                generate_dataset(output_path=str(DEFAULT_CSV_PATH))

            from scripts.import_traffic_csv_to_db import import_traffic_csv

            import_traffic_csv(csv_path=DEFAULT_CSV_PATH, session=db_session)

        # Query traffic data from database
        rows = db_session.exec(select(TrafficData)).all()
        if not rows:
            raise ValueError("Cannot train model: traffic_data table is empty.")

        X_list = []
        y_list = []
        for row in rows:
            features = [
                float(row.hour_of_day),
                float(row.day_of_week),
                float(row.is_weekend),
                float(row.is_rush_hour),
                float(row.weather_code),
                float(row.length_km),
                float(row.max_speed_limit),
            ]
            X_list.append(features)
            y_list.append(float(row.average_speed))

        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.float32)

        model = RandomForestRegressor(n_estimators=40, max_depth=10, random_state=42, n_jobs=-1)
        model.fit(X, y)
        r2_score = float(model.score(X, y))

        # Serialize model to bytes
        buffer = io.BytesIO()
        joblib.dump(model, buffer)
        model_bytes = buffer.getvalue()

        # Determine next version
        max_version = db_session.exec(
            select(func.max(MLModel.version)).where(MLModel.model_name == model_name)
        ).one_or_none()
        next_version = (max_version or 0) + 1

        # Deactivate previous active models
        db_session.exec(
            update(MLModel)
            .where(MLModel.model_name == model_name, MLModel.is_active == True)
            .values(is_active=False)
        )

        # Save new active model to database
        db_model = MLModel(
            model_name=model_name,
            version=next_version,
            model_bytes=model_bytes,
            metrics={"r2": round(r2_score, 4), "samples": len(rows)},
            is_active=True,
        )
        db_session.add(db_model)
        db_session.commit()
        db_session.refresh(db_model)

        logger.info(
            "Model '%s' v%d trained and saved to DB (samples=%d, r2=%.4f)",
            model_name,
            next_version,
            len(rows),
            r2_score,
        )
        return model, db_model

    finally:
        if owns_session:
            db_session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    model, db_entry = train_model()
    print(f"Model {db_entry.model_name} version {db_entry.version} successfully saved to database.")
