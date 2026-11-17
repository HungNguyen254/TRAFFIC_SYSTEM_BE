import uuid

from fastapi import APIRouter, Query, Request, status

from app.core.database import SessionDep
from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response
from app.schemas.routing import (
    AlternativesResult,
    RouteResult,
    SpeedSource,
    WeightMode,
)
from app.services.routing_service import (
    apply_speed_source,
    build_graph,
    find_route,
    find_route_alternatives,
)

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
    speed_source: SpeedSource = Query(  # noqa: B008
        "current",
        description="Nguồn tốc độ tính ETA: limit = giới hạn cố định, current = tốc độ hiện tại, forecast = dự báo",
    ),
):
    """Return the best route between two intersections as a standard envelope."""
    graph = build_graph(session, weight_mode)
    route = find_route(graph, origin_node_id, destination_node_id)
    apply_speed_source(session, route, speed_source)
    return success_response(request=request, message="Tìm tuyến thành công", data=route)


@router.get(
    "/alternatives",
    response_model=StandardResponse[AlternativesResult],
    status_code=status.HTTP_200_OK,
    summary="Đề xuất 2-3 tuyến khi tuyến chính có nguy cơ ùn tắc, so sánh ETA và mức ùn tắc",
)
@limiter.limit("20/minute")
def get_route_alternatives(
    request: Request,
    session: SessionDep,
    origin_node_id: uuid.UUID = Query(description="Nút giao chứa điểm đi"),  # noqa: B008
    destination_node_id: uuid.UUID = Query(description="Nút giao chứa điểm đến"),  # noqa: B008
    speed_source: SpeedSource = Query(  # noqa: B008
        "current",
        description="Nguồn tốc độ tính ETA: limit = giới hạn cố định, current = tốc độ hiện tại, forecast = dự báo",
    ),
):
    """Return the main route plus up to two alternatives when the main route is at risk."""
    result = find_route_alternatives(
        session, origin_node_id, destination_node_id, speed_source
    )
    return success_response(request=request, message="Đề xuất tuyến thành công", data=result)
