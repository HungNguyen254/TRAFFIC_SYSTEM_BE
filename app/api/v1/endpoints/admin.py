import logging
import threading
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status

from app.core.database import SessionDep
from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response
from app.core.security import get_current_admin
from app.models.user import User
from app.schemas.admin_road import (
    AdminRoadListResponse,
    AdminRoadPayload,
    AdminRoadResponse,
)
from app.schemas.admin_user import (
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdate,
)
from app.services.admin_user_service import AdminUserService
from app.services.prediction_service import PredictionService
from app.services.routing_service import clear_graph_cache
from app.services.traffic_service import TrafficService, clear_traffic_data_cache
from scripts.train_prediction_model import train_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


_retrain_lock = threading.Lock()


def _run_retraining() -> None:
    if not _retrain_lock.acquire(blocking=False):
        logger.warning("Model retraining already running in background, skipping duplicate request.")
        return
    try:
        train_model()
        PredictionService.reload_model()
        clear_traffic_data_cache()
        clear_graph_cache()
        logger.info("Background model retraining completed successfully.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Background model retraining failed: %s", exc)
    finally:
        _retrain_lock.release()


@router.post(
    "/retrain-model",
    response_model=StandardResponse[dict[str, str]],
    status_code=status.HTTP_200_OK,
    summary="Kích hoạt huấn luyện lại mô hình AI dự báo trong background (Admin)",
)
@limiter.limit("2/minute")
def trigger_retrain(
    request: Request,
    background_tasks: BackgroundTasks,
    _admin: Annotated[User, Depends(get_current_admin)],
):
    if _retrain_lock.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mô hình đang trong quá trình huấn luyện lại. Vui lòng chờ.",
        )
    background_tasks.add_task(_run_retraining)
    return success_response(
        request=request,
        message="Đã tiếp nhận yêu cầu huấn luyện lại mô hình trong tiến trình ngầm",
        data={"status": "processing", "message": "Model training running in background"},
    )


@router.get(
    "/users",
    response_model=StandardResponse[AdminUserListResponse],
    status_code=status.HTTP_200_OK,
    summary="Tìm kiếm tài khoản người dùng (Admin)",
)
@limiter.limit("30/minute")
def get_admin_users(
    request: Request,
    session: SessionDep,
    admin: Annotated[User, Depends(get_current_admin)],
    query: str = Query(default="", max_length=100),
):
    users = AdminUserService.list_users(session, query)
    return success_response(
        request=request,
        message=f"Tìm thấy {len(users.users)} tài khoản",
        data=users,
    )


@router.put(
    "/users/{user_id}",
    response_model=StandardResponse[AdminUserResponse],
    status_code=status.HTTP_200_OK,
    summary="Cập nhật thông tin hoặc quyền tài khoản (Admin)",
)
@limiter.limit("10/minute")
def update_admin_user(
    request: Request,
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    session: SessionDep,
    admin: Annotated[User, Depends(get_current_admin)],
):
    user = AdminUserService.update_user(session, user_id, payload, admin)
    return success_response(
        request=request,
        message=f"Đã cập nhật tài khoản {user.email}",
        data=user,
    )


@router.delete(
    "/users/{user_id}",
    response_model=StandardResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Xóa tài khoản người dùng (Admin)",
)
@limiter.limit("10/minute")
def delete_admin_user(
    request: Request,
    user_id: uuid.UUID,
    session: SessionDep,
    admin: Annotated[User, Depends(get_current_admin)],
):
    AdminUserService.delete_user(session, user_id, admin)
    return success_response(
        request=request,
        message="Đã xóa tài khoản người dùng",
        data=None,
    )


@router.get(
    "/roads",
    response_model=StandardResponse[AdminRoadListResponse],
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách đoạn đường phục vụ trang quản trị",
)
@limiter.limit("30/minute")
def get_admin_roads(
    request: Request,
    session: SessionDep,
    _admin: Annotated[User, Depends(get_current_admin)],
):
    roads = TrafficService.get_admin_roads(session)
    return success_response(
        request=request,
        message=f"Lấy {len(roads.roads)} đoạn đường thành công",
        data=roads,
    )


@router.post(
    "/roads",
    response_model=StandardResponse[AdminRoadResponse],
    status_code=status.HTTP_200_OK,
    summary="Tạo đoạn đường mới từ tuyến được vẽ (Admin)",
)
@limiter.limit("10/minute")
def create_admin_road(
    request: Request,
    payload: AdminRoadPayload,
    session: SessionDep,
    _admin: Annotated[User, Depends(get_current_admin)],
):
    road = TrafficService.create_admin_road(session, payload)
    clear_graph_cache()
    return success_response(
        request=request,
        message="Tạo đoạn đường thành công",
        data=road,
    )


@router.put(
    "/roads/{edge_id}",
    response_model=StandardResponse[AdminRoadResponse],
    status_code=status.HTTP_200_OK,
    summary="Cập nhật đoạn đường được vẽ (Admin)",
)
@limiter.limit("10/minute")
def update_admin_road(
    request: Request,
    edge_id: uuid.UUID,
    payload: AdminRoadPayload,
    session: SessionDep,
    _admin: Annotated[User, Depends(get_current_admin)],
):
    road = TrafficService.update_admin_road(session, edge_id, payload)
    clear_graph_cache()
    return success_response(
        request=request,
        message="Cập nhật đoạn đường thành công",
        data=road,
    )


@router.delete(
    "/roads/{edge_id}",
    response_model=StandardResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Xóa đoạn đường được quản trị (Admin)",
)
@limiter.limit("10/minute")
def delete_admin_road(
    request: Request,
    edge_id: uuid.UUID,
    session: SessionDep,
    _admin: Annotated[User, Depends(get_current_admin)],
):
    TrafficService.delete_admin_road(session, edge_id)
    clear_graph_cache()
    return success_response(
        request=request,
        message="Xóa đoạn đường thành công",
        data=None,
    )
