import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from zoneinfo import ZoneInfo

import networkx as nx
from sqlmodel import Session, select

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.edge import Edge
from app.models.node import Node
from app.schemas.routing import (
    AlternativesResult,
    RouteOption,
    RouteResult,
    RouteStep,
    SpeedSource,
    WeightMode,
)
from app.services.prediction_service import PredictionService
from app.services.traffic_service import TrafficService

MIN_SPEED_KMH = 1.0
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
RISK_CONGESTION_THRESHOLD = 2.5
GRAPH_CACHE_TTL_SECONDS = 300.0
_GRAPH_CACHE: dict[WeightMode, tuple[float, "TrafficGraph"]] = {}


def clear_graph_cache() -> None:
    """Clear all cached traffic graphs from memory."""
    _GRAPH_CACHE.clear()


@dataclass(frozen=True)
class TrafficGraph:
    network: nx.MultiDiGraph
    node_count: int
    edge_count: int
    skipped_edge_count: int


def _cheapest_edge(network: nx.Graph, start: uuid.UUID, end: uuid.UUID) -> dict:
    """Return the attributes of the cheapest edge between two adjacent nodes."""
    # Two Edge rows may share one node pair (parallel roads); Dijkstra costs the cheapest.
    data = network[start][end]
    if "weight" in data:
        return data
    return min(data.values(), key=lambda attrs: attrs["weight"])


def build_graph(
    session: Session,
    weight_mode: WeightMode = "distance",
    force_refresh: bool = False,
    ttl_seconds: float = GRAPH_CACHE_TTL_SECONDS,
) -> TrafficGraph:
    """Build a road graph whose edge cost is km, or minutes from legal limits in duration mode.
    
    Caches built graphs in memory by weight_mode to avoid redundant full-table DB scans.
    """
    now = time.monotonic()
    if not force_refresh and weight_mode in _GRAPH_CACHE:
        cached_time, cached_graph = _GRAPH_CACHE[weight_mode]
        if now - cached_time < ttl_seconds:
            return cached_graph
    nodes = list(session.exec(select(Node)).all())
    if not nodes:
        raise NotFoundException(
            message="Chưa có dữ liệu nút giao để dựng đồ thị!",
            error_code="GRAPH_EMPTY",
        )

    network = nx.MultiDiGraph()
    for node in nodes:
        network.add_node(
            node.node_id,
            node_code=node.node_code,
            node_name=node.node_name,
            latitude=node.latitude,
            longitude=node.longitude,
        )

    skipped = 0
    for edge in session.exec(select(Edge)).all():
        speed_kmh = float(edge.max_speed_limit)
        if edge.from_node_id == edge.to_node_id:
            skipped += 1
            continue
        if edge.length_km <= 0 or speed_kmh < MIN_SPEED_KMH:
            skipped += 1
            continue

        travel_min = edge.length_km / speed_kmh * 60
        if weight_mode == "duration":
            weight = travel_min
        else:
            weight = float(edge.length_km)

        network.add_edge(
            edge.from_node_id,
            edge.to_node_id,
            key=edge.edge_id,
            edge_id=edge.edge_id,
            edge_code=edge.edge_code,
            street_name=edge.street_name,
            length_km=edge.length_km,
            travel_min=travel_min,
            speed_kmh=speed_kmh,
            weight=weight,
        )

    traffic_graph = TrafficGraph(
        network=network,
        node_count=network.number_of_nodes(),
        edge_count=network.number_of_edges(),
        skipped_edge_count=skipped,
    )
    _GRAPH_CACHE[weight_mode] = (now, traffic_graph)
    return traffic_graph


def _validate_endpoints(
    network: nx.Graph, origin_node_id: uuid.UUID, destination_node_id: uuid.UUID
) -> None:
    if origin_node_id == destination_node_id:
        raise BadRequestException(
            message="Điểm đi và điểm đến trùng nhau!",
            error_code="ROUTE_SAME_ENDPOINT",
            details={"node_id": str(origin_node_id)},
        )

    if origin_node_id not in network or destination_node_id not in network:
        unknown = []
        if origin_node_id not in network:
            unknown.append(str(origin_node_id))
        if destination_node_id not in network:
            unknown.append(str(destination_node_id))
        raise BadRequestException(
            message="Không tìm thấy nút giao trong đồ thị!",
            error_code="ROUTE_NODE_NOT_FOUND",
            details={"unknown_node_ids": unknown},
        )


def _build_route(
    network: nx.Graph,
    origin_node_id: uuid.UUID,
    destination_node_id: uuid.UUID,
    node_path: list[uuid.UUID],
) -> RouteResult:
    steps = []
    for start, end in pairwise(node_path):
        attrs = _cheapest_edge(network, start, end)
        steps.append(
            RouteStep(
                edge_id=attrs["edge_id"],
                edge_code=attrs["edge_code"],
                street_name=attrs["street_name"],
                length_km=attrs["length_km"],
                travel_min=round(attrs["travel_min"], 2),
                speed_kmh=attrs["speed_kmh"],
            )
        )

    node_names = []
    polyline = []
    for node_id in node_path:
        data = network.nodes[node_id]
        node_names.append(data["node_name"])
        polyline.append([data["latitude"], data["longitude"]])

    return RouteResult(
        origin_node_id=origin_node_id,
        destination_node_id=destination_node_id,
        node_ids=node_path,
        node_names=node_names,
        edge_ids=[step.edge_id for step in steps],
        steps=steps,
        polyline=polyline,
        total_distance_km=round(sum(step.length_km for step in steps), 2),
        total_duration_min=round(sum(step.travel_min for step in steps), 2),
    )


def find_route(
    graph: TrafficGraph, origin_node_id: uuid.UUID, destination_node_id: uuid.UUID
) -> RouteResult:
    """Return the lowest-cost route between two nodes using Dijkstra on the graph."""
    network = graph.network
    _validate_endpoints(network, origin_node_id, destination_node_id)

    try:
        node_path = nx.dijkstra_path(
            network, origin_node_id, destination_node_id, weight="weight"
        )
    except nx.NetworkXNoPath as exc:
        raise NotFoundException(
            message="Không tìm được tuyến phù hợp giữa hai điểm đã chọn!",
            error_code="NO_ROUTE_FOUND",
            details={
                "reason": "one_way_disconnected",
                "origin_node_id": str(origin_node_id),
                "destination_node_id": str(destination_node_id),
            },
        ) from exc

    return _build_route(network, origin_node_id, destination_node_id, node_path)


def apply_speed_source(
    session: Session, route: RouteResult, speed_source: SpeedSource
) -> None:
    """Tính lại ETA từng đoạn theo tốc độ hiện tại hoặc dự báo thay vì giới hạn cố định."""
    if speed_source == "limit":
        for step in route.steps:
            step.congestion_level = 1
        return

    now_local = datetime.now(LOCAL_TZ)
    for step in route.steps:
        edge = session.get(Edge, step.edge_id)
        if speed_source == "current":
            snapshot = TrafficService.get_edge_traffic_snapshot(
                edge, now_local.hour, now_local.weekday(), session=session
            )
            speed, level = snapshot["speed"], snapshot["congestion_level"]
        else:
            speed, _risk, level, _desc = PredictionService._compute_prediction_values(
                edge=edge,
                hour_of_day=now_local.hour,
                day_of_week=now_local.weekday(),
            )
        speed = max(MIN_SPEED_KMH, min(speed, float(edge.max_speed_limit)))
        step.speed_kmh = speed
        step.congestion_level = level
        step.travel_min = round(step.length_km / speed * 60, 2)

    route.total_duration_min = round(sum(step.travel_min for step in route.steps), 2)


def _route_congestion_level(route: RouteResult) -> float:
    """Mức ùn tắc trung bình của tuyến, trọng số theo thời gian từng đoạn."""
    total_min = sum(step.travel_min for step in route.steps)
    if total_min <= 0:
        return 1.0
    weighted = sum(step.travel_min * (step.congestion_level or 1) for step in route.steps)
    return round(weighted / total_min, 2)


def _collapsed_network(graph: TrafficGraph) -> nx.DiGraph:
    """DiGraph mỗi cặp node một cạnh (cạnh rẻ nhất) để liệt kê tuyến bằng shortest_simple_paths."""
    network = graph.network
    simple = nx.DiGraph()
    simple.add_nodes_from((n, d) for n, d in network.nodes(data=True))
    for start, end, attrs in _cheapest_edges(network):
        simple.add_edge(start, end, **attrs)
    return simple


def _cheapest_edges(network: nx.MultiDiGraph):
    best: dict[tuple[uuid.UUID, uuid.UUID], dict] = {}
    for start, end, attrs in network.edges(data=True):
        current = best.get((start, end))
        if current is None or attrs["weight"] < current["weight"]:
            best[(start, end)] = attrs
    for (start, end), attrs in best.items():
        yield start, end, attrs


def find_route_alternatives(
    session: Session,
    origin_node_id: uuid.UUID,
    destination_node_id: uuid.UUID,
    speed_source: SpeedSource = "current",
    max_routes: int = 3,
) -> AlternativesResult:
    """Đề xuất tối đa max_routes tuyến khi tuyến chính có nguy cơ ùn tắc (ùn TB >= 2.5)."""
    graph = build_graph(session, weight_mode="duration")
    main_route = find_route(graph, origin_node_id, destination_node_id)
    apply_speed_source(session, main_route, speed_source)
    main_congestion = _route_congestion_level(main_route)
    main_at_risk = main_congestion >= RISK_CONGESTION_THRESHOLD

    options = [
        RouteOption(route=main_route, congestion_level=main_congestion, at_risk=main_at_risk)
    ]
    message = ""

    if main_at_risk:
        simple_network = _collapsed_network(graph)
        seen = {tuple(main_route.node_ids)}
        try:
            for node_path in nx.shortest_simple_paths(
                simple_network, origin_node_id, destination_node_id, weight="weight"
            ):
                if len(options) >= max_routes:
                    break
                path_key = tuple(node_path)
                if path_key in seen:
                    continue
                seen.add(path_key)
                alt_route = _build_route(
                    simple_network, origin_node_id, destination_node_id, list(node_path)
                )
                apply_speed_source(session, alt_route, speed_source)
                options.append(
                    RouteOption(
                        route=alt_route,
                        congestion_level=_route_congestion_level(alt_route),
                        at_risk=False,
                    )
                )
        except nx.NetworkXNoPath:
            pass
        options[1:] = sorted(options[1:], key=lambda opt: opt.route.total_duration_min)
        for option in options[1:]:
            option.at_risk = option.congestion_level >= RISK_CONGESTION_THRESHOLD
        if len(options) == 1:
            message = "Không tìm thấy tuyến đường khác giữa hai điểm đã chọn."

    return AlternativesResult(
        origin_node_id=origin_node_id,
        destination_node_id=destination_node_id,
        main_route_at_risk=main_at_risk,
        has_alternative=len(options) > 1,
        options=options,
        message=message,
    )
