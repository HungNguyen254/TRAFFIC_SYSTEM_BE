from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlmodel import Session, select

from app.models.segment import Segment
from app.models.observation import TrafficObservation
from app.schemas.forecast import ForecastResponse
from app.services.congestion import calculate_congestion_level

ALLOWED_HORIZONS = {15, 30, 45, 60}
MODEL_VERSION_BASELINE = "baseline-v1"


def get_current_time() -> datetime:
    """Dependency / helper to get current naive UTC datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Forecaster(ABC):
    @abstractmethod
    def forecast(
        self,
        segment: Segment,
        horizon_minutes: int,
        session: Session,
        now: Optional[datetime] = None,
    ) -> ForecastResponse:
        pass


class BaselineForecaster(Forecaster):
    def forecast(
        self,
        segment: Segment,
        horizon_minutes: int,
        session: Session,
        now: Optional[datetime] = None,
    ) -> ForecastResponse:
        if horizon_minutes not in ALLOWED_HORIZONS:
            raise ValueError(f"Invalid horizon {horizon_minutes}. Allowed: {ALLOWED_HORIZONS}")

        if now is None:
            now = get_current_time()
        elif now.tzinfo is not None:
            now = now.astimezone(timezone.utc).replace(tzinfo=None)

        target_time = now + timedelta(minutes=horizon_minutes)
        lookback_start = now - timedelta(days=56)  # 8 weeks before now

        # Query observations within the 8-week lookback window up to now
        statement = select(TrafficObservation).where(
            TrafficObservation.segment_id == segment.id,
            TrafficObservation.timestamp >= lookback_start,
            TrafficObservation.timestamp <= now,
        )
        observations = session.exec(statement).all()

        # Filter in Python for matching weekday and hour of the target time
        target_weekday = target_time.weekday()
        target_hour = target_time.hour

        matching_speeds = [
            obs.avg_speed_kmh
            for obs in observations
            if obs.timestamp.weekday() == target_weekday
            and obs.timestamp.hour == target_hour
        ]

        if matching_speeds:
            predicted_speed = round(sum(matching_speeds) / len(matching_speeds), 2)
        else:
            predicted_speed = segment.free_flow_speed_kmh

        congestion_level = calculate_congestion_level(
            predicted_speed, segment.free_flow_speed_kmh
        )

        return ForecastResponse(
            segment_id=segment.id,  # type: ignore[arg-type]
            target_time=target_time,
            predicted_speed_kmh=predicted_speed,
            congestion_level=congestion_level,
            model_version=MODEL_VERSION_BASELINE,
        )


baseline_forecaster = BaselineForecaster()
