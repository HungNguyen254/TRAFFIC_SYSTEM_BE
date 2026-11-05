from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.segment import Segment
from app.models.observation import TrafficObservation
from app.schemas.observation import ObservationCreate, ObservationBulkResponse

router = APIRouter(prefix="/observations", tags=["observations"])


@router.post("", response_model=ObservationBulkResponse, status_code=status.HTTP_200_OK)
def bulk_create_observations(
    observations_in: list[ObservationCreate],
    session: Session = Depends(get_session),
) -> ObservationBulkResponse:
    if not observations_in:
        return ObservationBulkResponse(inserted=0, skipped=0)

    # 1. Validate that all segment_ids exist in DB
    input_segment_ids = {obs.segment_id for obs in observations_in}
    statement = select(Segment.id).where(Segment.id.in_(input_segment_ids))  # type: ignore[attr-defined]
    existing_segment_ids = set(session.exec(statement).all())

    missing_segment_ids = input_segment_ids - existing_segment_ids
    if missing_segment_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"The following segment_id(s) do not exist: {sorted(list(missing_segment_ids))}",
        )

    # 2. Find range of timestamps in the batch for existing records lookup
    min_ts = min(obs.timestamp for obs in observations_in)
    max_ts = max(obs.timestamp for obs in observations_in)

    lookup_statement = select(
        TrafficObservation.segment_id,
        TrafficObservation.timestamp,
    ).where(
        TrafficObservation.segment_id.in_(input_segment_ids),  # type: ignore[attr-defined]
        TrafficObservation.timestamp >= min_ts,
        TrafficObservation.timestamp <= max_ts,
    )
    existing_pairs = set(session.exec(lookup_statement).all())

    # 3. Filter out records that already exist in DB or are duplicated in the batch
    seen_in_batch = set()
    to_insert: list[TrafficObservation] = []

    for obs in observations_in:
        pair = (obs.segment_id, obs.timestamp)
        if pair in existing_pairs or pair in seen_in_batch:
            continue
        seen_in_batch.add(pair)
        to_insert.append(TrafficObservation.model_validate(obs))

    if to_insert:
        session.add_all(to_insert)
        session.commit()

    inserted_count = len(to_insert)
    skipped_count = len(observations_in) - inserted_count

    return ObservationBulkResponse(inserted=inserted_count, skipped=skipped_count)
