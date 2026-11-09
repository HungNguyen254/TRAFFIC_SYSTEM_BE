from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.database import SessionDep
from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response
from app.core.security import get_optional_user
from app.models.user import User
from app.schemas.routing import RouteRequest, RouteResponse
from app.services.routing_service import RoutingService

router = APIRouter(prefix="/routing", tags=["routing"])


@router.post(
    "/directions",
    response_model=StandardResponse[RouteResponse],
    status_code=status.HTTP_200_OK,
    summary="Tìm kiếm lộ trình tối ưu và dự báo điểm tắc nghẽn",
)
@limiter.limit("20/minute")
def get_optimal_directions(
    request: Request,
    payload: RouteRequest,
    session: SessionDep,
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    result = RoutingService.calculate_optimal_route(session, payload, current_user)
    return success_response(
        request=request, message="Tìm kiếm lộ trình tối ưu thành công", data=result
    )
