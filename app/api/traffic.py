from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.segment import Segment
from app.models.observation import TrafficObservation
from app.schemas.traffic import CurrentTrafficRead
from app.services.congestion import calculate_congestion_level

router = APIRouter(prefix="/traffic", tags=["traffic"])


@router.get("/current", response_model=list[CurrentTrafficRead])
def get_current_traffic(
    session: Session = Depends(get_session),
) -> list[CurrentTrafficRead]:
    # Portable query: find max timestamp per segment, join to get the observation and free_flow_speed
    subquery = (
        select(
            TrafficObservation.segment_id,
            func.max(TrafficObservation.timestamp).label("max_ts"),
        )
        .group_by(TrafficObservation.segment_id)
        .subquery()
    )

    statement = (
        select(TrafficObservation, Segment.free_flow_speed_kmh)
        .join(
            subquery,
            (TrafficObservation.segment_id == subquery.c.segment_id)
            & (TrafficObservation.timestamp == subquery.c.max_ts),
        )
        .join(Segment, Segment.id == TrafficObservation.segment_id)
    )

    rows = session.exec(statement).all()

    results: list[CurrentTrafficRead] = []
    for obs, free_flow_speed in rows:
        congestion_level = calculate_congestion_level(
            obs.avg_speed_kmh, free_flow_speed
        )
        results.append(
            CurrentTrafficRead(
                segment_id=obs.segment_id,
                timestamp=obs.timestamp,
                avg_speed_kmh=obs.avg_speed_kmh,
                vehicle_count=obs.vehicle_count,
                congestion_level=congestion_level,
            )
        )
    return results
