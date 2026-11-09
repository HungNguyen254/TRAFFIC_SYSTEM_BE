import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.database import SessionDep
from app.core.response import StandardResponse, success_response
from app.core.security import get_current_admin
from app.models.user import User
from app.schemas.traffic import NodeCreate, NodeResponse, NodeUpdate
from app.services.traffic_service import TrafficService

router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.get(
    "",
    response_model=StandardResponse[list[NodeResponse]],
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách các nút giao thông",
)
def list_nodes(
    request: Request,
    session: SessionDep,
    district: Annotated[str | None, Query(description="Lọc theo quận")] = None,
):
    nodes = TrafficService.list_nodes(session, district)
    return success_response(
        request=request, message="Lấy danh sách nút giao thành công", data=nodes
    )


@router.get(
    "/search",
    response_model=StandardResponse[list[NodeResponse]],
    status_code=status.HTTP_200_OK,
    summary="Tìm kiếm nút giao theo tên hoặc mã",
)
def search_nodes(
    request: Request,
    session: SessionDep,
    query: Annotated[str, Query(min_length=1, description="Từ khóa tên hoặc mã nút giao")],
):
    nodes = TrafficService.resolve_node_by_name(session, query)
    return success_response(request=request, message="Tìm kiếm nút giao thành công", data=nodes)


@router.get(
    "/{node_id}",
    response_model=StandardResponse[NodeResponse],
    status_code=status.HTTP_200_OK,
    summary="Lấy chi tiết một nút giao",
)
def get_node(request: Request, session: SessionDep, node_id: uuid.UUID):
    node = TrafficService.get_node_by_id(session, node_id)
    return success_response(request=request, message="Lấy thông tin nút giao thành công", data=node)


@router.post(
    "",
    response_model=StandardResponse[NodeResponse],
    status_code=status.HTTP_200_OK,
    summary="Tạo mới một nút giao (Admin)",
)
def create_node(
    request: Request,
    payload: NodeCreate,
    session: SessionDep,
    _admin: Annotated[User, Depends(get_current_admin)],
):
    node = TrafficService.create_node(session, payload)
    return success_response(request=request, message="Tạo nút giao thành công", data=node)


@router.put(
    "/{node_id}",
    response_model=StandardResponse[NodeResponse],
    status_code=status.HTTP_200_OK,
    summary="Cập nhật thông tin nút giao (Admin)",
)
def update_node(
    request: Request,
    node_id: uuid.UUID,
    payload: NodeUpdate,
    session: SessionDep,
    _admin: Annotated[User, Depends(get_current_admin)],
):
    node = TrafficService.update_node(session, node_id, payload)
    return success_response(request=request, message="Cập nhật nút giao thành công", data=node)


@router.delete(
    "/{node_id}",
    response_model=StandardResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Xóa một nút giao (Admin)",
)
def delete_node(
    request: Request,
    node_id: uuid.UUID,
    session: SessionDep,
    _admin: Annotated[User, Depends(get_current_admin)],
):
    TrafficService.delete_node(session, node_id)
    return success_response(request=request, message="Xóa nút giao thành công", data=None)
