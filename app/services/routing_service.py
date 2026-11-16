import time
import uuid
from dataclasses import dataclass
from itertools import pairwise

import networkx as nx
from sqlmodel import Session, select

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.edge import Edge
from app.models.node import Node
from app.schemas.routing import RouteResult, RouteStep, WeightMode

MIN_SPEED_KMH = 1.0
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


def _cheapest_edge(network: nx.MultiDiGraph, start: uuid.UUID, end: uuid.UUID) -> dict:
    """Return the attributes of the cheapest edge between two adjacent nodes."""
    # Two Edge rows may share one node pair (parallel roads); Dijkstra costs the cheapest.
    return min(network[start][end].values(), key=lambda attrs: attrs["weight"])


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


def find_route(
    graph: TrafficGraph, origin_node_id: uuid.UUID, destination_node_id: uuid.UUID
) -> RouteResult:
    """Return the lowest-cost route between two nodes using Dijkstra on the graph."""
    network = graph.network

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

    steps = []
    for start, end in pairwise(node_path):
        attrs = _cheapest_edge(network, start, end)
        step = RouteStep(
            edge_id=attrs["edge_id"],
            edge_code=attrs["edge_code"],
            street_name=attrs["street_name"],
            length_km=attrs["length_km"],
            travel_min=round(attrs["travel_min"], 2),
            speed_kmh=attrs["speed_kmh"],
        )
        steps.append(step)

    node_names = []
    polyline = []
    for node_id in node_path:
        data = network.nodes[node_id]
        node_names.append(data["node_name"])
        polyline.append([data["latitude"], data["longitude"]])

    total_distance_km = round(sum(step.length_km for step in steps), 2)
    total_duration_min = round(sum(step.travel_min for step in steps), 2)

    return RouteResult(
        origin_node_id=origin_node_id,
        destination_node_id=destination_node_id,
        node_ids=node_path,
        node_names=node_names,
        edge_ids=[step.edge_id for step in steps],
        steps=steps,
        polyline=polyline,
        total_distance_km=total_distance_km,
        total_duration_min=total_duration_min,
    )
