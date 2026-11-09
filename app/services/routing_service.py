import itertools
import logging
import uuid
from datetime import UTC, datetime

import networkx as nx
from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.edge import Edge
from app.models.node import Node
from app.models.search_history import SearchHistory
from app.models.user import User
from app.schemas.routing import RouteRequest, RouteResponse, RouteSegmentDetail
from app.schemas.traffic import NodeResponse
from app.services.prediction_service import PredictionService
from app.services.traffic_service import TrafficService

logger = logging.getLogger(__name__)


class RoutingService:
    @staticmethod
    def _resolve_endpoint_node(
        session: Session, node_id: uuid.UUID | None, node_name: str | None, role: str
    ) -> Node:
        if node_id:
            node = session.get(Node, node_id)
            if node:
                return node
        if node_name:
            candidates = TrafficService.resolve_node_by_name(session, node_name)
            if candidates:
                return candidates[0]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không xác định được điểm {role} ('{node_name or node_id}') trên mạng lưới giao thông Hà Nội.",
        )

    @classmethod
    def calculate_optimal_route(
        cls, session: Session, payload: RouteRequest, current_user: User | None = None
    ) -> RouteResponse:
        origin_node = cls._resolve_endpoint_node(
            session, payload.origin_id, payload.origin_name, "xuất phát"
        )
        dest_node = cls._resolve_endpoint_node(
            session, payload.destination_id, payload.destination_name, "đích"
        )

        if origin_node.node_id == dest_node.node_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Điểm xuất phát và điểm đến không được trùng nhau.",
            )

        # Build NetworkX graph
        edges = session.exec(select(Edge)).all()
        G = nx.DiGraph()

        # Cache nodes
        all_nodes = {n.node_id: n for n in session.exec(select(Node)).all()}

        edge_map = {}
        for edge in edges:
            pred = PredictionService.predict_for_edge(
                session=session,
                edge=edge,
                hour_of_day=payload.hour_of_day,
                day_of_week=payload.day_of_week,
                weather=payload.weather,
            )

            # Cost weight = (hours of travel) * (penalty for congestion risk)
            travel_hours = edge.length_km / max(pred.predicted_speed, 5.0)
            weight = travel_hours * (1.0 + pred.risk_factor * 2.0)

            G.add_edge(
                edge.from_node_id,
                edge.to_node_id,
                weight=weight,
                edge_obj=edge,
                prediction=pred,
            )
            edge_map[(edge.from_node_id, edge.to_node_id)] = (edge, pred)

        # Find shortest path using Dijkstra
        try:
            path_node_ids = nx.shortest_path(
                G, source=origin_node.node_id, target=dest_node.node_id, weight="weight"
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy lộ trình kết nối giữa 2 điểm này trên đồ thị.",
            ) from exc

        path_nodes = [
            NodeResponse(
                node_id=all_nodes[nid].node_id,
                node_code=all_nodes[nid].node_code,
                node_name=all_nodes[nid].node_name,
                district=all_nodes[nid].district,
                latitude=all_nodes[nid].latitude,
                longitude=all_nodes[nid].longitude,
                geom=all_nodes[nid].geom,
                created_at=all_nodes[nid].created_at,
            )
            for nid in path_node_ids
        ]

        total_distance = 0.0
        total_time_minutes = 0.0
        segments = []
        congested_streets = []

        for u, v in itertools.pairwise(path_node_ids):
            edge, pred = edge_map[(u, v)]
            total_distance += edge.length_km
            travel_minutes = (edge.length_km / max(pred.predicted_speed, 5.0)) * 60.0
            total_time_minutes += travel_minutes

            if pred.congestion_level >= 3:
                congested_streets.append(f"{edge.street_name} (Mức {pred.congestion_level}/4)")

            segments.append(
                RouteSegmentDetail(
                    edge_id=edge.edge_id,
                    street_name=edge.street_name,
                    length_km=edge.length_km,
                    predicted_speed=pred.predicted_speed,
                    risk_factor=pred.risk_factor,
                    congestion_level=pred.congestion_level,
                )
            )

        warning = None
        if congested_streets:
            warning = f"Lưu ý: Có nguy cơ ùn ứ trên các đoạn: {', '.join(congested_streets)}"

        # Save to SearchHistory table
        history = SearchHistory(
            user_id=current_user.user_id if current_user else None,
            origin_name=origin_node.node_name,
            origin_lat=origin_node.latitude,
            origin_lng=origin_node.longitude,
            destination_name=dest_node.node_name,
            destination_lat=dest_node.latitude,
            destination_lng=dest_node.longitude,
            searched_at=datetime.now(UTC),
        )
        session.add(history)
        session.commit()

        return RouteResponse(
            origin=path_nodes[0],
            destination=path_nodes[-1],
            nodes=path_nodes,
            segments=segments,
            total_distance_km=round(total_distance, 2),
            estimated_time_minutes=round(total_time_minutes, 1),
            congestion_warning=warning,
        )
