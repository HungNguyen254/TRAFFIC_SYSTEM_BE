import uuid

from fastapi import APIRouter, Query, Request, status

from app.core.database import SessionDep
from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response
from app.schemas.routing import RouteResult, WeightMode
from app.services.routing_service import build_graph, find_route

router = APIRouter(prefix="/directions", tags=["directions"])


@router.get(
    "",
    response_model=StandardResponse[RouteResult],
    status_code=status.HTTP_200_OK,
    summary="Tìm tuyến từ điểm đi đến điểm đến: polyline, quãng đường, các đoạn đi qua",
)
@limiter.limit("20/minute")
def get_directions(
    request: Request,
    session: SessionDep,
    origin_node_id: uuid.UUID = Query(description="Nút giao chứa điểm đi"),  # noqa: B008
    destination_node_id: uuid.UUID = Query(description="Nút giao chứa điểm đến"),  # noqa: B008
    weight_mode: WeightMode = Query(  # noqa: B008
        "distance",
        description="distance = ưu tiên ngắn nhất theo km, duration = ưu tiên nhanh nhất theo phút",
    ),
):
    """Return the best route between two intersections as a standard envelope."""
    graph = build_graph(session, weight_mode)
    route = find_route(graph, origin_node_id, destination_node_id)
    return success_response(request=request, message="Tìm tuyến thành công", data=route)
