from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.core.auth import get_current_user, require_admin
from app.core.database import get_session
from app.models.segment import Segment
from app.models.observation import TrafficObservation
from app.models.user import User
from app.schemas.segment import SegmentCreate, SegmentRead, SegmentUpdate
from app.schemas.observation import ObservationRead, ensure_naive_utc

router = APIRouter(prefix="/segments", tags=["segments"])


@router.get("", response_model=list[SegmentRead])
def list_segments(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[Segment]:
    statement = select(Segment).offset(offset).limit(limit)
    return list(session.exec(statement).all())


@router.get("/{id}", response_model=SegmentRead)
def get_segment(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Segment:
    segment = session.get(Segment, id)
    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment with id {id} not found",
        )
    return segment


@router.post("", response_model=SegmentRead, status_code=status.HTTP_201_CREATED)
def create_segment(
    segment_in: SegmentCreate,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin),
) -> Segment:
    segment = Segment.model_validate(segment_in)
    session.add(segment)
    session.commit()
    session.refresh(segment)
    return segment


@router.put("/{id}", response_model=SegmentRead)
def update_segment(
    id: int,
    segment_in: SegmentUpdate,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin),
) -> Segment:
    segment = session.get(Segment, id)
    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment with id {id} not found",
        )

    update_data = segment_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(segment, field, value)

    session.add(segment)
    session.commit()
    session.refresh(segment)
    return segment


@router.delete("/{id}")
def delete_segment(
    id: int,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin),
) -> dict[str, str]:
    segment = session.get(Segment, id)
    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment with id {id} not found",
        )

    # Clean up associated observations first to preserve foreign key integrity
    from sqlmodel import delete
    session.exec(delete(TrafficObservation).where(TrafficObservation.segment_id == id))

    session.delete(segment)
    session.commit()
    return {"message": "Segment deleted successfully"}


@router.get("/{id}/history", response_model=list[ObservationRead])
def get_segment_history(
    id: int,
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[TrafficObservation]:
    segment = session.get(Segment, id)
    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment with id {id} not found",
        )

    statement = select(TrafficObservation).where(TrafficObservation.segment_id == id)

    if start is not None:
        statement = statement.where(TrafficObservation.timestamp >= ensure_naive_utc(start))
    if end is not None:
        statement = statement.where(TrafficObservation.timestamp <= ensure_naive_utc(end))

    statement = statement.order_by(TrafficObservation.timestamp.asc()).limit(limit)
    return list(session.exec(statement).all())
