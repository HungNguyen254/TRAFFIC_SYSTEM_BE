import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.database import SessionDep
from app.core.response import StandardResponse, success_response
from app.core.security import get_current_admin
from app.models.user import User
from app.schemas.traffic_record import TrafficRecordResponse, TrafficRecordUpdate
from app.services.traffic_record_service import TrafficRecordService

router = APIRouter(prefix="/traffic-records", tags=["traffic-records"])


@router.post(
    "/update",
    response_model=StandardResponse[TrafficRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="Cập nhật trạng thái giao thông thời gian thực trên đoạn đường (Admin/Simulator)",
)
def update_traffic_record(
    request: Request,
    payload: TrafficRecordUpdate,
    session: SessionDep,
    _admin: Annotated[User, Depends(get_current_admin)],
):
    record = TrafficRecordService.update_record(session, payload)
    return success_response(
        request=request, message="Cập nhật trạng thái giao thông thành công", data=record
    )


@router.get(
    "/latest",
    response_model=StandardResponse[list[TrafficRecordResponse]],
    status_code=status.HTTP_200_OK,
    summary="Lấy trạng thái giao thông mới nhất trên các đoạn đường",
)
def get_latest_traffic_records(
    request: Request,
    session: SessionDep,
    edge_id: Annotated[uuid.UUID | None, Query(description="Lọc theo đoạn đường cụ thể")] = None,
):
    records = TrafficRecordService.get_latest_records(session, edge_id)
    return success_response(
        request=request, message="Lấy dữ liệu trạng thái giao thông thành công", data=records
    )
