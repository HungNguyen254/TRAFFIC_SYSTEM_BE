from fastapi import APIRouter, Request, status

from app.core.database import SessionDep
from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response
from app.schemas.prediction import (
    MapForecastRequest,
    MapForecastResponse,
    PredictionRequest,
    PredictionResponse,
)
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["predictions"])


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
):
    result = PredictionService.get_map_forecast(session, payload)
    return success_response(
        request=request,
        message=f"Dự báo giao thông toàn bản đồ sau {result.minutes_ahead} phút thành công",
        data=result,
    )
