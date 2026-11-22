from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import Annotated

from app.core.database import SessionDep
from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.prediction import (
    MapForecastRequest,
    MapForecastResponse,
    PredictionRequest,
    PredictionResponse,
    RouteForecastRequest,
    RouteForecastResponse,
)
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["predictions"])


def require_premium_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Tính năng chỉ dành cho tài khoản Premium."""
    if current_user.plan != "premium":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tính năng này chỉ dành cho tài khoản Premium. Vui lòng nâng cấp gói để sử dụng.",
        )
    return current_user


@router.post(
    "/forecast",
    response_model=StandardResponse[PredictionResponse],
    status_code=status.HTTP_200_OK,
    summary="Dự báo mức độ tắc đường và tốc độ di chuyển theo dòng thời gian tương lai (30, 60, 120 phút...)",
)
@limiter.limit("10/minute")
def get_traffic_forecast(
    request: Request,
    payload: PredictionRequest,
    session: SessionDep,
):
    result = PredictionService.get_forecast(session, payload)
    return success_response(
        request=request, message="Dự báo tình trạng giao thông thành công", data=result
    )


@router.post(
    "/forecast/route",
    response_model=StandardResponse[RouteForecastResponse],
    status_code=status.HTTP_200_OK,
    summary="Dự báo ETA theo từng đoạn của một tuyến đường",
)
@limiter.limit("10/minute")
def get_route_traffic_forecast(
    request: Request,
    payload: RouteForecastRequest,
    session: SessionDep,
    _: Annotated[User, Depends(require_premium_user)],
):
    result = PredictionService.get_route_forecast(session, payload)
    return success_response(
        request=request,
        message="Dự báo ETA tuyến đường thành công",
        data=result,
    )


@router.post(
    "/forecast/map",
    response_model=StandardResponse[MapForecastResponse],
    status_code=status.HTTP_200_OK,
    summary="Dự báo tình trạng giao thông trên toàn bản đồ",
)
@limiter.limit("10/minute")
def get_map_traffic_forecast(
    request: Request,
    payload: MapForecastRequest,
    session: SessionDep,
    _: Annotated[User, Depends(require_premium_user)],
):
    result = PredictionService.get_map_forecast(session, payload)
    return success_response(
        request=request,
        message=f"Dự báo giao thông toàn bản đồ sau {result.minutes_ahead} phút thành công",
        data=result,
    )
