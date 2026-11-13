import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.database import SessionDep
from app.core.response import StandardResponse, success_response
from app.core.security import get_current_admin
from app.models.user import User
from app.schemas.traffic import EdgeCreate, EdgeResponse, EdgeUpdate
from app.services.traffic_service import TrafficService

router = APIRouter(prefix="/edges", tags=["edges"])


@router.get(
    "",
    response_model=StandardResponse[list[EdgeResponse]],
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách các đoạn đường",
)
def list_edges(
    request: Request,
    session: SessionDep,
    street_name: Annotated[str | None, Query(description="Lọc theo tên đường")] = None,
):
    edges = TrafficService.list_edges(session, street_name)
    return success_response(
        request=request, message="Lấy danh sách đoạn đường thành công", data=edges
    )


@router.get(
    "/{edge_id}",
    response_model=StandardResponse[EdgeResponse],
    status_code=status.HTTP_200_OK,
    summary="Lấy chi tiết một đoạn đường",
)
def get_edge(request: Request, session: SessionDep, edge_id: uuid.UUID):
    edge = TrafficService.get_edge_by_id(session, edge_id)
    return success_response(
        request=request, message="Lấy thông tin đoạn đường thành công", data=edge
    )


@router.post(
    "",
    response_model=StandardResponse[EdgeResponse],
    status_code=status.HTTP_200_OK,
    summary="Tạo mới một đoạn đường (Admin)",
)
def create_edge(
    request: Request,
    payload: EdgeCreate,
    session: SessionDep,
    _admin: Annotated[User, Depends(get_current_admin)],
):
    edge = TrafficService.create_edge(session, payload)
    return success_response(request=request, message="Tạo đoạn đường thành công", data=edge)


@router.put(
    "/{edge_id}",
    response_model=StandardResponse[EdgeResponse],
    status_code=status.HTTP_200_OK,
    summary="Cập nhật thông tin đoạn đường (Admin)",
)
def update_edge(
    request: Request,
    edge_id: uuid.UUID,
    payload: EdgeUpdate,
    session: SessionDep,
    _admin: Annotated[User, Depends(get_current_admin)],
):
    edge = TrafficService.update_edge(session, edge_id, payload)
    return success_response(request=request, message="Cập nhật đoạn đường thành công", data=edge)


@router.delete(
    "/{edge_id}",
    response_model=StandardResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Xóa một đoạn đường (Admin)",
)
def delete_edge(
    request: Request,
    edge_id: uuid.UUID,
    session: SessionDep,
    _admin: Annotated[User, Depends(get_current_admin)],
):
    TrafficService.delete_edge(session, edge_id)
    return success_response(request=request, message="Xóa đoạn đường thành công", data=None)
