from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.database import SessionDep
from app.core.response import StandardResponse, success_response
from app.core.security import get_current_admin, get_current_user
from app.models.user import User
from app.schemas.search_history import SearchHistoryResponse, SearchStatsResponse
from app.services.user_data_service import UserDataService

router = APIRouter(prefix="/search-histories", tags=["search-histories"])


@router.get(
    "/me",
    response_model=StandardResponse[list[SearchHistoryResponse]],
    status_code=status.HTTP_200_OK,
    summary="Lấy lịch sử tra cứu lộ trình cá nhân của người dùng",
)
def get_my_search_histories(
    request: Request,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    histories = UserDataService.list_user_search_history(session, current_user.user_id, limit)
    return success_response(
        request=request, message="Lấy lịch sử tra cứu thành công", data=histories
    )


@router.delete(
    "/me",
    response_model=StandardResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Xóa toàn bộ lịch sử tra cứu lộ trình cá nhân",
)
def clear_my_search_histories(
    request: Request,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    UserDataService.clear_user_search_history(session, current_user.user_id)
    return success_response(request=request, message="Xóa lịch sử thành công", data=None)


@router.get(
    "/stats",
    response_model=StandardResponse[SearchStatsResponse],
    status_code=status.HTTP_200_OK,
    summary="Thống kê tổng số lượt tìm kiếm và các điểm đến phổ biến (Admin)",
)
def get_search_statistics(
    request: Request,
    session: SessionDep,
    _admin: Annotated[User, Depends(get_current_admin)],
):
    stats = UserDataService.get_search_stats(session)
    return success_response(
        request=request, message="Lấy dữ liệu thống kê tra cứu thành công", data=stats
    )
