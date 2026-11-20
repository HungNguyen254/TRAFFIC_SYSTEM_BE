"""Train Traffic Congestion Machine Learning Model using data from database, compare MAE with baseline, and persist model."""

import io
import logging
import sys
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib
import numpy as np
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sqlalchemy import func, update
from sqlmodel import Session, select

from app.core.database import engine, init_db
from app.models.ml_model import MLModel
from app.models.traffic_data import TrafficData

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "traffic_speed_rf"
DEFAULT_CSV_PATH = Path("data/synthetic_traffic_dataset.csv")
DEFAULT_MODEL_FILE_PATH = Path("models/traffic_model.joblib")


def evaluate_and_compare_models(
    X: np.ndarray,
    y: np.ndarray,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict:
    """Evaluate and compare Baseline, Linear Regression, and Random Forest models on test split."""
    if len(X) < 5:
        # If very small dataset, train and test on the same data to avoid split errors
        X_train, X_test, y_train, y_test = X, X, y, y
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )

    # 1. Baseline Model (predict mean target)
    baseline = DummyRegressor(strategy="mean")
    baseline.fit(X_train, y_train)
    y_pred_base = baseline.predict(X_test)

    # 2. Linear Regression
    lr = LinearRegression()
    lr.fit(X_train, y_train)
    y_pred_lr = lr.predict(X_test)

    # 3. Random Forest Regressor
    rf = RandomForestRegressor(n_estimators=40, max_depth=10, random_state=random_state, n_jobs=-1)
    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_test)

    def _calc_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
        return {
            "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
            "rmse": round(float(root_mean_squared_error(y_true, y_pred)), 4),
            "r2": round(float(r2_score(y_true, y_pred)), 4),
        }

    results = {
        "baseline": _calc_metrics(y_test, y_pred_base),
        "linear_regression": _calc_metrics(y_test, y_pred_lr),
        "random_forest": _calc_metrics(y_test, y_pred_rf),
        "samples_train": int(len(X_train)),
        "samples_test": int(len(X_test)),
    }

    # Relative MAE improvement of Random Forest over Baseline
    base_mae = results["baseline"]["mae"]
    rf_mae = results["random_forest"]["mae"]
    if base_mae > 0:
        improvement = ((base_mae - rf_mae) / base_mae) * 100.0
        results["mae_improvement_pct"] = round(improvement, 2)
    else:
        results["mae_improvement_pct"] = 0.0

    return results


def train_model(
    session: Session | None = None,
    model_name: str = DEFAULT_MODEL_NAME,
    save_file_path: Path | str | None = None,
) -> tuple[RandomForestRegressor, MLModel, dict]:
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

        # Query traffic feature columns directly from database
        query = select(
            TrafficData.hour_of_day,
            TrafficData.day_of_week,
            TrafficData.is_weekend,
            TrafficData.is_rush_hour,
            TrafficData.weather_code,
            TrafficData.length_km,
            TrafficData.max_speed_limit,
            TrafficData.average_speed,
        )
        rows = db_session.exec(query).all()
        if not rows:
            raise ValueError("Cannot train model: traffic_data table is empty.")

        X_list = []
        y_list = []
        for row in rows:
            features = [
                float(row[0]),
                float(row[1]),
                float(row[2]),
                float(row[3]),
                float(row[4]),
                float(row[5]),
                float(row[6]),
            ]
            X_list.append(features)
            y_list.append(float(row[7]))

        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.float32)

        # Evaluate models on train/test split and compare MAE with baseline
        eval_metrics = evaluate_and_compare_models(X, y)
        logger.info(
            "Evaluation complete: Baseline MAE=%.4f, LR MAE=%.4f, RF MAE=%.4f (Improvement: %.2f%%)",
            eval_metrics["baseline"]["mae"],
            eval_metrics["linear_regression"]["mae"],
            eval_metrics["random_forest"]["mae"],
            eval_metrics["mae_improvement_pct"],
        )

        # Train final production model on full data
        model = RandomForestRegressor(n_estimators=40, max_depth=10, random_state=42, n_jobs=-1)
        model.fit(X, y)

        # Save model file to disk if requested (prevent in-memory test sessions from clobbering production file)
        target_path = save_file_path if save_file_path is not None else DEFAULT_MODEL_FILE_PATH
        should_save = (save_file_path is not None) or (owns_session and target_path is not None)
        if should_save and target_path:
            out_file = Path(target_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(model, out_file, compress=3)
            logger.info("Persisted model file to %s", out_file)

        # Serialize model to bytes for database persistence
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
        db_metrics = {
            "r2": eval_metrics["random_forest"]["r2"],
            "mae": eval_metrics["random_forest"]["mae"],
            "rmse": eval_metrics["random_forest"]["rmse"],
            "baseline_mae": eval_metrics["baseline"]["mae"],
            "linear_regression_mae": eval_metrics["linear_regression"]["mae"],
            "mae_improvement_pct": eval_metrics["mae_improvement_pct"],
            "samples": len(rows),
        }
        db_model = MLModel(
            model_name=model_name,
            version=next_version,
            model_bytes=model_bytes,
            metrics=db_metrics,
            is_active=True,
        )
        db_session.add(db_model)
        db_session.commit()
        db_session.refresh(db_model)

        logger.info(
            "Model '%s' v%d trained and saved to DB (samples=%d, mae=%.4f, baseline_mae=%.4f, r2=%.4f)",
            model_name,
            next_version,
            len(rows),
            db_metrics["mae"],
            db_metrics["baseline_mae"],
            db_metrics["r2"],
        )
        return model, db_model, eval_metrics

    finally:
        if owns_session:
            db_session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    model, db_entry, metrics = train_model()

    print("\n" + "=" * 70)
    print("🚦 BÁO CÁO ĐÁNH GIÁ MÔ HÌNH DỰ BÁO TỐC ĐỘ GIAO THÔNG (TRAFFIC SPEED)")
    print("=" * 70)
    print(f"{'Mô hình':<25} | {'MAE (km/h)':<12} | {'RMSE (km/h)':<12} | {'R² Score':<10}")
    print("-" * 70)
    print(
        f"{'Baseline (Mean)':<25} | {metrics['baseline']['mae']:<12.4f} | {metrics['baseline']['rmse']:<12.4f} | {metrics['baseline']['r2']:<10.4f}"
    )
    print(
        f"{'Linear Regression':<25} | {metrics['linear_regression']['mae']:<12.4f} | {metrics['linear_regression']['rmse']:<12.4f} | {metrics['linear_regression']['r2']:<10.4f}"
    )
    print(
        f"{'Random Forest Regressor':<25} | {metrics['random_forest']['mae']:<12.4f} | {metrics['random_forest']['rmse']:<12.4f} | {metrics['random_forest']['r2']:<10.4f}"
    )
    print("=" * 70)
    print(
        f"🎯 Random Forest cải thiện {metrics['mae_improvement_pct']:.2f}% MAE so với Baseline (Dummy Mean)."
    )
    print(f"💾 File mô hình được lưu tại: {DEFAULT_MODEL_FILE_PATH}")
    print(
        f"🗄️  Bản ghi DB: MLModel(model_name='{db_entry.model_name}', version={db_entry.version}, is_active={db_entry.is_active})"
    )
    print("=" * 70 + "\n")
