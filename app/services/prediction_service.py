import io
import logging
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import joblib
import numpy as np
from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.core.database import engine
from app.models.edge import Edge
from app.models.ml_model import MLModel
from app.models.prediction import Prediction
from app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
    PredictionTimelineItem,
)

logger = logging.getLogger(__name__)

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class PredictionService:
    _model = None
    _lock = threading.Lock()

    @classmethod
    def load_model(cls, session: Session | None = None) -> None:
        owns_session = session is None
        db_session = Session(engine) if owns_session else session
        try:
            try:
                statement = (
                    select(MLModel)
                    .where(MLModel.model_name == "traffic_speed_rf", MLModel.is_active == True)
                    .order_by(MLModel.version.desc())
                )
                db_model = db_session.exec(statement).first()
            except Exception as db_err:  # noqa: BLE001
                logger.warning(
                    "Database query error while loading ML model: %s. Preserving existing model state.",
                    db_err,
                )
                return

            if db_model and db_model.model_bytes:
                try:
                    new_model = joblib.load(io.BytesIO(db_model.model_bytes))
                    cls._model = new_model
                    logger.info(
                        "Successfully loaded ML model '%s' v%d from database",
                        db_model.model_name,
                        db_model.version,
                    )
                except Exception as deser_err:  # noqa: BLE001
                    logger.warning(
                        "Failed to deserialize ML model bytes from database: %s. Using heuristic fallback.",
                        deser_err,
                    )
                    cls._model = None
            else:
                logger.info(
                    "No active ML model found in database. Using heuristic fallback."
                )
                cls._model = None
        finally:
            if owns_session:
                db_session.close()

    @classmethod
    def reload_model(cls) -> None:
        with cls._lock:
            cls.load_model()

    @staticmethod
    def _weather_to_code(weather: str) -> float:
        w = weather.lower().strip()
        if "heavy" in w or "ngập" in w or "to" in w:
            return 2.0
        elif "rain" in w or "mưa" in w:
            return 1.0
        return 0.0

    @classmethod
    def _compute_prediction_values(
        cls,
        edge: Edge,
        hour_of_day: int,
        day_of_week: int = 0,
        weather: str = "sunny",
    ) -> tuple[float, float, int, str]:
        is_weekend = 1.0 if day_of_week in (5, 6) else 0.0
        is_rush_hour = 1.0 if (7 <= hour_of_day <= 9 or 17 <= hour_of_day <= 19) else 0.0
        weather_code = cls._weather_to_code(weather)

        model = cls._model
        if model is not None:
            features = np.array(
                [
                    [
                        float(hour_of_day),
                        float(day_of_week),
                        is_weekend,
                        is_rush_hour,
                        weather_code,
                        float(edge.length_km),
                        float(edge.max_speed_limit),
                    ]
                ],
                dtype=np.float32,
            )
            predicted_speed = float(model.predict(features)[0])
        else:
            # Heuristic fallback
            factor = 0.85
            if is_rush_hour and not is_weekend:
                factor -= 0.45
            elif is_rush_hour and is_weekend:
                factor -= 0.20
            if weather_code == 1.0:
                factor -= 0.15
            elif weather_code == 2.0:
                factor -= 0.30
            factor = max(0.15, min(0.95, factor))
            predicted_speed = edge.max_speed_limit * factor

        predicted_speed = max(5.0, min(float(edge.max_speed_limit), round(predicted_speed, 1)))
        speed_ratio = predicted_speed / float(edge.max_speed_limit)
        risk_factor = round(max(0.0, min(1.0, 1.0 - speed_ratio)), 2)

        if predicted_speed >= 35.0:
            congestion_level = 1
            desc = "Đường rất thông thoáng, di chuyển thuận lợi"
        elif predicted_speed >= 25.0:
            congestion_level = 2
            desc = "Lưu lượng bình thường, tốc độ ổn định"
        elif predicted_speed >= 15.0:
            congestion_level = 3
            desc = "Đông đúc, nguy cơ ùn ứ vào khung giờ này"
        else:
            congestion_level = 4
            desc = "Tắc nghẽn nghiêm trọng, nên chọn lộ trình tránh"

        return predicted_speed, risk_factor, congestion_level, desc

    @classmethod
    def _save_or_update_prediction(
        cls,
        session: Session,
        edge_id: uuid.UUID,
        hour_of_day: int,
        predicted_speed: float,
        risk_factor: float,
        now: datetime,
    ) -> None:
        db_prediction = session.exec(
            select(Prediction).where(
                Prediction.edge_id == edge_id,
                Prediction.hour_of_day == hour_of_day,
            )
        ).first()

        if db_prediction:
            db_prediction.predicted_speed = predicted_speed
            db_prediction.risk_factor = risk_factor
            db_prediction.updated_at = now
        else:
            db_prediction = Prediction(
                edge_id=edge_id,
                hour_of_day=hour_of_day,
                predicted_speed=predicted_speed,
                risk_factor=risk_factor,
                updated_at=now,
            )
            session.add(db_prediction)

    @classmethod
    def predict_for_edge(
        cls,
        session: Session,
        edge: Edge,
        hour_of_day: int,
        day_of_week: int = 0,
        weather: str = "sunny",
    ) -> PredictionTimelineItem:
        predicted_speed, risk_factor, congestion_level, desc = cls._compute_prediction_values(
            edge=edge,
            hour_of_day=hour_of_day,
            day_of_week=day_of_week,
            weather=weather,
        )
        now = datetime.now(UTC)
        cls._save_or_update_prediction(
            session=session,
            edge_id=edge.edge_id,
            hour_of_day=hour_of_day,
            predicted_speed=predicted_speed,
            risk_factor=risk_factor,
            now=now,
        )
        session.commit()

        return PredictionTimelineItem(
            minutes_ahead=0,
            target_time=now,
            hour_of_day=hour_of_day,
            day_of_week=day_of_week,
            predicted_speed=predicted_speed,
            max_speed_limit=edge.max_speed_limit,
            risk_factor=risk_factor,
            congestion_level=congestion_level,
            description=desc,
        )

    @classmethod
    def get_forecast(cls, session: Session, payload: PredictionRequest) -> PredictionResponse:
        edge = None
        if payload.edge_id:
            edge = session.get(Edge, payload.edge_id)
        elif payload.street_name:
            query = select(Edge).where(Edge.street_name.ilike(f"%{payload.street_name.strip()}%"))
            edge = session.exec(query).first()

        if not edge:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đoạn đường yêu cầu dự báo.",
            )

        base_time = payload.base_time or datetime.now(UTC)
        sorted_minutes = sorted(set(payload.minutes_ahead))

        now = datetime.now(UTC)
        timeline_items: list[PredictionTimelineItem] = []

        for offset in sorted_minutes:
            target_time = base_time + timedelta(minutes=offset)
            if target_time.tzinfo is None:
                local_target = target_time.replace(tzinfo=UTC).astimezone(LOCAL_TZ)
            else:
                local_target = target_time.astimezone(LOCAL_TZ)

            target_hour = local_target.hour
            target_day = local_target.weekday()

            speed, risk, level, desc = cls._compute_prediction_values(
                edge=edge,
                hour_of_day=target_hour,
                day_of_week=target_day,
                weather=payload.weather,
            )

            timeline_items.append(
                PredictionTimelineItem(
                    minutes_ahead=offset,
                    target_time=target_time,
                    hour_of_day=target_hour,
                    day_of_week=target_day,
                    predicted_speed=speed,
                    max_speed_limit=edge.max_speed_limit,
                    risk_factor=risk,
                    congestion_level=level,
                    description=desc,
                )
            )

        return PredictionResponse(
            edge_id=edge.edge_id,
            street_name=edge.street_name,
            max_speed_limit=edge.max_speed_limit,
            base_time=base_time,
            weather=payload.weather,
            timeline=timeline_items,
            updated_at=now,
        )
