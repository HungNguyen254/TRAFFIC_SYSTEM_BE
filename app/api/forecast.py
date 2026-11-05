from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.segment import Segment
from app.schemas.forecast import ForecastResponse
from app.services.forecasting import (
    ALLOWED_HORIZONS,
    baseline_forecaster,
    get_current_time,
)
from app.services.ml_forecaster import ml_forecaster

router = APIRouter(prefix="/forecast", tags=["forecast"])


def get_clock() -> datetime:
    """Dependency providing the current time for deterministic testing."""
    return get_current_time()


@router.get("/map", response_model=list[ForecastResponse])
def get_forecast_map(
    horizon: int = Query(...),
    model: str = Query(default="ml", pattern="^(ml|baseline)$"),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_clock),
) -> list[ForecastResponse]:
    if horizon not in ALLOWED_HORIZONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid horizon {horizon}. Allowed values: {sorted(list(ALLOWED_HORIZONS))}",
        )

    forecaster = ml_forecaster if model == "ml" else baseline_forecaster
    segments = session.exec(select(Segment)).all()

    return [
        forecaster.forecast(
            segment=segment,
            horizon_minutes=horizon,
            session=session,
            now=now,
        )
        for segment in segments
    ]


@router.get("", response_model=ForecastResponse)
def get_forecast(
    segment_id: int = Query(...),
    horizon: int = Query(...),
    model: str = Query(default="ml", pattern="^(ml|baseline)$"),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_clock),
) -> ForecastResponse:
    if horizon not in ALLOWED_HORIZONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid horizon {horizon}. Allowed values: {sorted(list(ALLOWED_HORIZONS))}",
        )

    segment = session.get(Segment, segment_id)
    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment with id {segment_id} not found",
        )

    forecaster = ml_forecaster if model == "ml" else baseline_forecaster

    return forecaster.forecast(
        segment=segment,
        horizon_minutes=horizon,
        session=session,
        now=now,
    )
