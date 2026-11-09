import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.database import SessionDep
from app.core.response import StandardResponse, success_response
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.saved_place import SavedPlaceCreate, SavedPlaceResponse
from app.services.user_data_service import UserDataService

router = APIRouter(prefix="/saved-places", tags=["saved-places"])


@router.post(
    "",
    response_model=StandardResponse[SavedPlaceResponse],
    status_code=status.HTTP_200_OK,
    summary="Lưu địa điểm yêu thích (Nhà, Công ty...)",
)
def create_saved_place(
    request: Request,
    payload: SavedPlaceCreate,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    place = UserDataService.create_saved_place(session, current_user.user_id, payload)
    return success_response(request=request, message="Lưu địa điểm thành công", data=place)


@router.get(
    "",
    response_model=StandardResponse[list[SavedPlaceResponse]],
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách các địa điểm đã lưu của người dùng",
)
def list_saved_places(
    request: Request,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    places = UserDataService.list_saved_places(session, current_user.user_id)
    return success_response(
        request=request, message="Lấy danh sách địa điểm đã lưu thành công", data=places
    )


@router.delete(
    "/{saved_place_id}",
    response_model=StandardResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Xóa địa điểm đã lưu",
)
def delete_saved_place(
    request: Request,
    saved_place_id: uuid.UUID,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    UserDataService.delete_saved_place(session, current_user.user_id, saved_place_id)
    return success_response(request=request, message="Xóa địa điểm thành công", data=None)
