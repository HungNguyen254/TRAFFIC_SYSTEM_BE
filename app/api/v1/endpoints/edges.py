import uuid
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.database import SessionDep
from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response
from app.core.security import get_current_admin
from app.models.user import User
from app.schemas.edge_status import EdgeStatusResponse, parse_bbox_param
from app.schemas.traffic import EdgeCreate, EdgeResponse, EdgeUpdate
from app.services.traffic_service import TrafficService

router = APIRouter(prefix="/edges", tags=["edges"])

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


@router.get(
    "/status",
    response_model=StandardResponse[EdgeStatusResponse],
    status_code=status.HTTP_200_OK,
    summary="Tình trạng mới nhất của các đoạn đường theo khung bản đồ (bounding box) hoặc theo khu vực",
)
@limiter.limit("60/minute")
def get_edges_status(
    request: Request,
    session: SessionDep,
    bbox: str | None = Query(
        default=None,
        description="Khung bản đồ định dạng 'min_lng,min_lat,max_lng,max_lat' hoặc 'min_lat,min_lng,max_lat,max_lng'",
    ),
    min_lat: float | None = Query(default=None, description="Vĩ độ nhỏ nhất (South)"),
    min_lng: float | None = Query(default=None, description="Kinh độ nhỏ nhất (West)"),
    max_lat: float | None = Query(default=None, description="Vĩ độ lớn nhất (North)"),
    max_lng: float | None = Query(default=None, description="Kinh độ lớn nhất (East)"),
    district: str | None = Query(default=None, description="Quận/Huyện cần lọc (vd: Đống Đa, Cầu Giấy, hoặc không dấu)"),
    area: str | None = Query(default=None, description="Khu vực (alias cho district)"),
    hour: int | None = Query(default=None, ge=0, le=23, description="Giờ cần tra (mặc định: giờ hiện tại)"),
    day_of_week: int | None = Query(default=None, ge=0, le=6, description="0=T2 ... 6=CN (mặc định: hôm nay)"),
):
    try:
        parsed_min_lat, parsed_min_lng, parsed_max_lat, parsed_max_lng = parse_bbox_param(
            bbox=bbox,
            min_lat=min_lat,
            min_lng=min_lng,
            max_lat=max_lat,
            max_lng=max_lng,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    selected_district = district or area

    now_local = datetime.now(LOCAL_TZ)
    h = hour if hour is not None else now_local.hour
    d = day_of_week if day_of_week is not None else now_local.weekday()

    data = TrafficService.get_edges_status(
        session=session,
        min_lat=parsed_min_lat,
        min_lng=parsed_min_lng,
        max_lat=parsed_max_lat,
        max_lng=parsed_max_lng,
        district=selected_district,
        hour_of_day=h,
        day_of_week=d,
    )

    return success_response(
        request=request,
        message=f"Lấy tình trạng của {data.total} đoạn đường thành công",
        data=data,
    )


@router.get(
    "",
    response_model=StandardResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Danh sách nodes + edges kèm mức giao thông (hỗ trợ lọc bounding box hoặc khu vực)",
)
@limiter.limit("30/minute")
def get_edges_with_traffic(
    request: Request,
    session: SessionDep,
    bbox: str | None = Query(
        default=None,
        description="Khung bản đồ định dạng 'min_lng,min_lat,max_lng,max_lat' hoặc 'min_lat,min_lng,max_lat,max_lng'",
    ),
    min_lat: float | None = Query(default=None, description="Vĩ độ nhỏ nhất (South)"),
    min_lng: float | None = Query(default=None, description="Kinh độ nhỏ nhất (West)"),
    max_lat: float | None = Query(default=None, description="Vĩ độ lớn nhất (North)"),
    max_lng: float | None = Query(default=None, description="Kinh độ lớn nhất (East)"),
    district: str | None = Query(default=None, description="Quận/Huyện cần lọc"),
    area: str | None = Query(default=None, description="Khu vực (alias cho district)"),
    hour: int | None = Query(default=None, ge=0, le=23, description="Giờ cần tra (mặc định: giờ hiện tại)"),
    day_of_week: int | None = Query(default=None, ge=0, le=6, description="0=T2 ... 6=CN (mặc định: hôm nay)"),
):
    try:
        parsed_min_lat, parsed_min_lng, parsed_max_lat, parsed_max_lng = parse_bbox_param(
            bbox=bbox,
            min_lat=min_lat,
            min_lng=min_lng,
            max_lat=max_lat,
            max_lng=max_lng,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    selected_district = district or area

    now_local = datetime.now(LOCAL_TZ)
    h = hour if hour is not None else now_local.hour
    d = day_of_week if day_of_week is not None else now_local.weekday()

    data = TrafficService.get_edges_with_traffic(
        session=session,
        hour_of_day=h,
        day_of_week=d,
        min_lat=parsed_min_lat,
        min_lng=parsed_min_lng,
        max_lat=parsed_max_lat,
        max_lng=parsed_max_lng,
        district=selected_district,
    )
    return success_response(
        request=request,
        message=f"Lấy {len(data['edges'])} edges ({len(data['nodes'])} nodes) cho giờ {h}, thứ {d + 1}",
        data=data,
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
