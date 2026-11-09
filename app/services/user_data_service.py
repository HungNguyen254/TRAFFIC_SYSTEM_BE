import uuid
from collections import Counter

from fastapi import HTTPException, status
from sqlmodel import Session, col, desc, select

from app.models.saved_place import SavedPlace
from app.models.search_history import SearchHistory
from app.schemas.saved_place import SavedPlaceCreate
from app.schemas.search_history import DestinationCount, SearchStatsResponse


class UserDataService:
    @staticmethod
    def create_saved_place(
        session: Session, user_id: uuid.UUID, payload: SavedPlaceCreate
    ) -> SavedPlace:
        place = SavedPlace(user_id=user_id, **payload.model_dump())
        session.add(place)
        session.commit()
        session.refresh(place)
        return place

    @staticmethod
    def list_saved_places(session: Session, user_id: uuid.UUID) -> list[SavedPlace]:
        stmt = (
            select(SavedPlace)
            .where(SavedPlace.user_id == user_id)
            .order_by(col(SavedPlace.created_at).desc())
        )
        return list(session.exec(stmt).all())

    @staticmethod
    def delete_saved_place(session: Session, user_id: uuid.UUID, saved_place_id: uuid.UUID) -> None:
        place = session.get(SavedPlace, saved_place_id)
        if not place or place.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy địa điểm đã lưu cần xóa.",
            )
        session.delete(place)
        session.commit()

    @staticmethod
    def list_user_search_history(
        session: Session, user_id: uuid.UUID, limit: int = 20
    ) -> list[SearchHistory]:
        stmt = (
            select(SearchHistory)
            .where(SearchHistory.user_id == user_id)
            .order_by(desc(SearchHistory.searched_at))
            .limit(limit)
        )
        return list(session.exec(stmt).all())

    @staticmethod
    def clear_user_search_history(session: Session, user_id: uuid.UUID) -> None:
        stmt = select(SearchHistory).where(SearchHistory.user_id == user_id)
        records = session.exec(stmt).all()
        for r in records:
            session.delete(r)
        session.commit()

    @staticmethod
    def get_search_stats(session: Session) -> SearchStatsResponse:
        records = session.exec(select(SearchHistory)).all()
        total_searches = len(records)

        counter = Counter(r.destination_name for r in records if r.destination_name)
        top = [
            DestinationCount(destination_name=dest, count=cnt)
            for dest, cnt in counter.most_common(10)
        ]
        return SearchStatsResponse(
            total_searches=total_searches,
            top_destinations=top,
        )
