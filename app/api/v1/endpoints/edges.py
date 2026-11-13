from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.core.database import SessionDep
from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response
from app.schemas.edge_status import EdgeStatusResponse, parse_bbox_param
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
