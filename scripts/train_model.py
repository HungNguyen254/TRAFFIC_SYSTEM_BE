import os
import sys
from datetime import timedelta
import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sqlmodel import Session, select

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import engine
from app.models.segment import Segment
from app.models.observation import TrafficObservation
from app.services.features import FEATURE_COLUMNS, extract_features

HORIZONS = [15, 30, 45, 60]
MODEL_OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "app", "services", "ml_model.joblib"
)


def build_dataset() -> tuple[list[dict], list[float]]:
    X_rows: list[dict] = []
    y_vals: list[float] = []

    with Session(engine) as session:
        segments = session.exec(select(Segment)).all()

        for seg in segments:
            observations = session.exec(
                select(TrafficObservation)
                .where(TrafficObservation.segment_id == seg.id)
                .order_by(TrafficObservation.timestamp.asc())
            ).all()

            if len(observations) < 5:
                continue

            ts_map = {obs.timestamp: obs.avg_speed_kmh for obs in observations}

            for i in range(2, len(observations)):
                obs_0 = observations[i]
                obs_1 = observations[i - 1]
                obs_2 = observations[i - 2]

                # Check that observations are within 60 minutes window
                if (obs_0.timestamp - obs_2.timestamp) > timedelta(minutes=60):
                    continue

                recent_obs = [obs_0, obs_1, obs_2]

                for horizon in HORIZONS:
                    target_time = obs_0.timestamp + timedelta(minutes=horizon)
                    if target_time in ts_map:
                        target_speed = ts_map[target_time]
                        feats = extract_features(seg, target_time, horizon, recent_obs)
                        X_rows.append(feats)
                        y_vals.append(target_speed)

    return X_rows, y_vals


def train_and_save_model() -> None:
    print("Collecting observations from database...")
    X_dicts, y_list = build_dataset()

    if len(X_dicts) < 50:
        raise ValueError(f"Insufficient training samples ({len(X_dicts)}). Please run seed script first.")

    print(f"Collected {len(X_dicts)} training samples.")

    y = np.array(y_list)

    pipeline = Pipeline(
        steps=[
            ("vectorizer", DictVectorizer(sparse=False)),
            ("regressor", HistGradientBoostingRegressor(max_iter=150, random_state=42)),
        ]
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X_dicts, y, test_size=0.15, random_state=42
    )

    print("Training pipeline...")
    pipeline.fit(X_train, y_train)

    preds = pipeline.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = root_mean_squared_error(y_test, preds)
    print(f"Test Evaluation — MAE: {mae:.2f} km/h, RMSE: {rmse:.2f} km/h")

    # Fit on all data before saving
    pipeline.fit(X_dicts, y)

    os.makedirs(os.path.dirname(MODEL_OUTPUT_PATH), exist_ok=True)
    joblib.dump(pipeline, MODEL_OUTPUT_PATH)
    print(f"Model successfully saved to {MODEL_OUTPUT_PATH}")


if __name__ == "__main__":
    train_and_save_model()
