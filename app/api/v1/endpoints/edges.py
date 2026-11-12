from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query, Request, status

from app.core.database import SessionDep
from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response
from app.services.traffic_service import TrafficService

router = APIRouter(prefix="/edges", tags=["edges"])

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


@router.get(
    "",
    response_model=StandardResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Danh sách nodes + edges kèm mức giao thông (tính từ dataset CSV theo giờ hiện tại)",
)
@limiter.limit("30/minute")
def get_edges_with_traffic(
    request: Request,
    session: SessionDep,
    hour: int | None = Query(default=None, ge=0, le=23, description="Giờ cần tra (mặc định: giờ hiện tại)"),
    day_of_week: int | None = Query(default=None, ge=0, le=6, description="0=T2 ... 6=CN (mặc định: hôm nay)"),
):
    now_local = datetime.now(LOCAL_TZ)
    h = hour if hour is not None else now_local.hour
    d = day_of_week if day_of_week is not None else now_local.weekday()

    data = TrafficService.get_edges_with_traffic(session, hour_of_day=h, day_of_week=d)
    return success_response(
        request=request,
        message=f"Lấy {len(data['edges'])} edges ({len(data['nodes'])} nodes) cho giờ {h}, thứ {d + 1}",
        data=data,
    )
