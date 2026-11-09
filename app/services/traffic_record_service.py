import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.edge import Edge
from app.models.traffic_record import TrafficRecord
from app.schemas.traffic_record import TrafficRecordUpdate


class TrafficRecordService:
    @staticmethod
    def calculate_congestion(speed: float) -> tuple[int, str]:
        if speed >= 35.0:
            return 1, "#22c55e"
        elif speed >= 25.0:
            return 2, "#eab308"
        elif speed >= 15.0:
            return 3, "#f97316"
        else:
            return 4, "#ef4444"

    @staticmethod
    def update_record(session: Session, payload: TrafficRecordUpdate) -> TrafficRecord:
        edge = session.get(Edge, payload.edge_id)
        if not edge:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy đoạn đường có ID {payload.edge_id}.",
            )

        auto_level, auto_color = TrafficRecordService.calculate_congestion(payload.current_speed)
        level = payload.congestion_level if payload.congestion_level is not None else auto_level
        color = payload.color_code if payload.color_code else auto_color

        record = session.exec(
            select(TrafficRecord).where(TrafficRecord.edge_id == payload.edge_id)
        ).first()

        if record:
            record.current_speed = payload.current_speed
            record.congestion_level = level
            record.color_code = color
            record.updated_at = datetime.now(UTC)
        else:
            record = TrafficRecord(
                edge_id=payload.edge_id,
                current_speed=payload.current_speed,
                congestion_level=level,
                color_code=color,
                updated_at=datetime.now(UTC),
            )
            session.add(record)

        session.commit()
        session.refresh(record)
        return record

    @staticmethod
    def get_latest_records(
        session: Session, edge_id: uuid.UUID | None = None
    ) -> list[TrafficRecord]:
        stmt = select(TrafficRecord)
        if edge_id:
            stmt = stmt.where(TrafficRecord.edge_id == edge_id)
        return list(session.exec(stmt).all())
