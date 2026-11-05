import logging
import os
from datetime import UTC, datetime, timedelta

import joblib
from sqlmodel import Session, select

from app.models.observation import TrafficObservation
from app.models.segment import Segment
from app.schemas.forecast import ForecastResponse
from app.services.congestion import calculate_congestion_level
from app.services.features import extract_features
from app.services.forecasting import (
    ALLOWED_HORIZONS,
    Forecaster,
    baseline_forecaster,
    get_current_time,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), "ml_model.joblib")
MODEL_VERSION_ML = "ml-v1"


class MLForecaster(Forecaster):
    def __init__(self, model_path: str | None = None):
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        if os.path.exists(self.model_path):
            try:
                self._model = joblib.load(self.model_path)
                logger.info("ML model successfully loaded from %s", self.model_path)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Failed to load ML model from %s: %s", self.model_path, e
                )
                self._model = None
        else:
            logger.info("ML model file %s does not exist yet.", self.model_path)
            self._model = None

    def forecast(
        self,
        segment: Segment,
        horizon_minutes: int,
        session: Session,
        now: datetime | None = None,
    ) -> ForecastResponse:
        if horizon_minutes not in ALLOWED_HORIZONS:
            raise ValueError(
                f"Invalid horizon {horizon_minutes}. Allowed: {ALLOWED_HORIZONS}"
            )

        if now is None:
            now = get_current_time()
        elif now.tzinfo is not None:
            now = now.astimezone(UTC).replace(tzinfo=None)

        # 1. Fallback if model artifact is not loaded
        if self._model is None:
            # Try reloading once in case it was generated recently
            self._load_model()
            if self._model is None:
                logger.info(
                    "Falling back to baseline-v1 because ML model artifact is missing."
                )
                return baseline_forecaster.forecast(
                    segment=segment,
                    horizon_minutes=horizon_minutes,
                    session=session,
                    now=now,
                )

        # 2. Query up to 3 recent observations within the last 60 minutes
        window_start = now - timedelta(minutes=60)
        statement = (
            select(TrafficObservation)
            .where(
                TrafficObservation.segment_id == segment.id,
                TrafficObservation.timestamp >= window_start,
                TrafficObservation.timestamp <= now,
            )
            .order_by(TrafficObservation.timestamp.desc())
            .limit(3)
        )
        recent_obs = list(session.exec(statement).all())

        # 3. Data sufficiency guard: must have at least 3 observations in recent window
        if len(recent_obs) < 3:
            logger.info(
                "Segment %s has fewer than 3 recent observations (%d found). Falling back to baseline-v1.",
                segment.id,
                len(recent_obs),
            )
            return baseline_forecaster.forecast(
                segment=segment,
                horizon_minutes=horizon_minutes,
                session=session,
                now=now,
            )

        # 4. Staleness guard: newest observation must not be older than 45 minutes
        obs_ts = recent_obs[0].timestamp
        if obs_ts.tzinfo is not None:
            obs_ts = obs_ts.astimezone(UTC).replace(tzinfo=None)
        newest_obs_age = now - obs_ts
        if newest_obs_age > timedelta(minutes=45):
            logger.info(
                "Segment %s newest observation is stale (age: %s > 45m). Falling back to baseline-v1.",
                segment.id,
                newest_obs_age,
            )
            return baseline_forecaster.forecast(
                segment=segment,
                horizon_minutes=horizon_minutes,
                session=session,
                now=now,
            )

        # 5. Extract features and predict
        target_time = now + timedelta(minutes=horizon_minutes)
        features = extract_features(
            segment=segment,
            target_time=target_time,
            horizon_minutes=horizon_minutes,
            recent_observations=recent_obs,
        )

        try:
            preds = self._model.predict([features])
            raw_speed = float(preds[0])
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ML prediction failed: %s. Falling back to baseline-v1.", exc
            )
            return baseline_forecaster.forecast(
                segment=segment,
                horizon_minutes=horizon_minutes,
                session=session,
                now=now,
            )

        # 6. Clamp predicted speed: at least 5.0 km/h, at most 110% of free_flow_speed
        max_speed = segment.free_flow_speed_kmh * 1.1
        predicted_speed = round(max(5.0, min(raw_speed, max_speed)), 2)

        congestion_level = calculate_congestion_level(
            predicted_speed, segment.free_flow_speed_kmh
        )

        return ForecastResponse(
            segment_id=segment.id,  # type: ignore[arg-type]
            target_time=target_time,
            predicted_speed_kmh=predicted_speed,
            congestion_level=congestion_level,
            model_version=MODEL_VERSION_ML,
        )


ml_forecaster = MLForecaster()
