from datetime import datetime
from typing import Any
from app.models.segment import Segment
from app.models.observation import TrafficObservation

FEATURE_COLUMNS = [
    "target_hour",
    "target_weekday",
    "is_weekend",
    "is_rush_hour",
    "horizon_minutes",
    "free_flow_speed_kmh",
    "length_m",
    "road_type",
    "lag_speed_0",
    "lag_speed_1",
    "lag_speed_2",
    "speed_trend",
]


def is_rush_hour(hour: int) -> int:
    """Morning rush: 7-9h, Evening rush: 17-19h."""
    return 1 if (7 <= hour < 9 or 17 <= hour < 19) else 0


def extract_features(
    segment: Segment,
    target_time: datetime,
    horizon_minutes: int,
    recent_observations: list[TrafficObservation],
) -> dict[str, Any]:
    """
    Extract ML features from a segment, target_time, horizon, and up to 3 recent observations.
    recent_observations must be ordered from newest to oldest: [obs_0, obs_1, obs_2].
    """
    target_hour = target_time.hour
    target_weekday = target_time.weekday()
    is_weekend_val = 1 if target_weekday >= 5 else 0
    is_rush = is_rush_hour(target_hour)

    lag_0 = recent_observations[0].avg_speed_kmh if len(recent_observations) > 0 else segment.free_flow_speed_kmh
    lag_1 = recent_observations[1].avg_speed_kmh if len(recent_observations) > 1 else lag_0
    lag_2 = recent_observations[2].avg_speed_kmh if len(recent_observations) > 2 else lag_1

    speed_trend = round(lag_0 - lag_1, 2)

    return {
        "target_hour": target_hour,
        "target_weekday": target_weekday,
        "is_weekend": is_weekend_val,
        "is_rush_hour": is_rush,
        "horizon_minutes": horizon_minutes,
        "free_flow_speed_kmh": float(segment.free_flow_speed_kmh),
        "length_m": float(segment.length_m),
        "road_type": str(segment.road_type),
        "lag_speed_0": float(lag_0),
        "lag_speed_1": float(lag_1),
        "lag_speed_2": float(lag_2),
        "speed_trend": float(speed_trend),
    }
