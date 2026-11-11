"""Train Traffic Congestion Machine Learning Model on synthetic dataset without pandas dependency."""

import csv
import sys
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor

DATA_PATH = Path("data/synthetic_traffic_dataset.csv")
MODEL_PATH = Path("app/core/model.joblib")


def train_model(
    csv_path: Path = DATA_PATH, model_save_path: Path = MODEL_PATH
) -> RandomForestRegressor:
    if not csv_path.exists():
        from scripts.generate_synthetic_traffic import generate_dataset

        generate_dataset(output_path=str(csv_path))

    X_list = []
    y_list = []

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            features = [
                float(row["hour_of_day"]),
                float(row["day_of_week"]),
                float(row["is_weekend"]),
                float(row["is_rush_hour"]),
                float(row["weather_code"]),
                float(row["length_km"]),
                float(row["max_speed_limit"]),
            ]
            X_list.append(features)
            y_list.append(float(row["average_speed"]))

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)

    model = RandomForestRegressor(n_estimators=40, max_depth=10, random_state=42, n_jobs=-1)
    model.fit(X, y)

    model_save_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_save_path)
    print(f"Model trained successfully and saved to {model_save_path}")
    return model


if __name__ == "__main__":
    train_model()
