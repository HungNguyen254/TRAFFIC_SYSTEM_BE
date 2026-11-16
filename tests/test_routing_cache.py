import uuid
from unittest.mock import MagicMock
import pytest
from sqlmodel import Session

from app.models.edge import Edge
from app.models.node import Node
from app.services.routing_service import build_graph, clear_graph_cache


def test_build_graph_caches_result():
    clear_graph_cache()
    mock_session = MagicMock(spec=Session)

    node1 = Node(
        node_id=uuid.uuid4(),
        node_code="N1",
        node_name="Node 1",
        latitude=21.0,
        longitude=105.8,
    )
    node2 = Node(
        node_id=uuid.uuid4(),
        node_code="N2",
        node_name="Node 2",
        latitude=21.1,
        longitude=105.9,
    )
    edge = Edge(
        edge_id=uuid.uuid4(),
        edge_code="E1",
        street_name="Street 1",
        from_node_id=node1.node_id,
        to_node_id=node2.node_id,
        length_km=1.5,
        max_speed_limit=40,
    )

    mock_session.exec.side_effect = [
        MagicMock(all=lambda: [node1, node2]),
        MagicMock(all=lambda: [edge]),
        MagicMock(all=lambda: [node1, node2]),
        MagicMock(all=lambda: [edge]),
    ]

    # First call: executes queries
    g1 = build_graph(mock_session, weight_mode="distance")
    assert mock_session.exec.call_count == 2
    assert g1.node_count == 2
    assert g1.edge_count == 1

    # Second call with same weight_mode: served from cache, no DB queries executed
    g2 = build_graph(mock_session, weight_mode="distance")
    assert g1 is g2
    assert mock_session.exec.call_count == 2

    # Clear cache and verify rebuild
    clear_graph_cache()
    g3 = build_graph(mock_session, weight_mode="distance")
    assert mock_session.exec.call_count == 4
    assert g3 is not g1


def test_build_graph_weight_modes_cached_independently():
    clear_graph_cache()
    mock_session = MagicMock(spec=Session)

    node1 = Node(node_id=uuid.uuid4(), node_code="N1", node_name="N1", latitude=21.0, longitude=105.8)
    node2 = Node(node_id=uuid.uuid4(), node_code="N2", node_name="N2", latitude=21.1, longitude=105.9)
    edge = Edge(edge_id=uuid.uuid4(), edge_code="E1", street_name="S1", from_node_id=node1.node_id, to_node_id=node2.node_id, length_km=1.0, max_speed_limit=60)

    mock_session.exec.side_effect = [
        MagicMock(all=lambda: [node1, node2]),
        MagicMock(all=lambda: [edge]),
        MagicMock(all=lambda: [node1, node2]),
        MagicMock(all=lambda: [edge]),
    ]

    g_dist = build_graph(mock_session, weight_mode="distance")
    g_dur = build_graph(mock_session, weight_mode="duration")

    assert g_dist is not g_dur
    assert mock_session.exec.call_count == 4

    # Now both are cached, no additional queries
    assert build_graph(mock_session, weight_mode="distance") is g_dist
    assert build_graph(mock_session, weight_mode="duration") is g_dur
    assert mock_session.exec.call_count == 4


def test_build_graph_force_refresh():
    clear_graph_cache()
    mock_session = MagicMock(spec=Session)

    node1 = Node(node_id=uuid.uuid4(), node_code="N1", node_name="N1", latitude=21.0, longitude=105.8)
    node2 = Node(node_id=uuid.uuid4(), node_code="N2", node_name="N2", latitude=21.1, longitude=105.9)
    edge = Edge(edge_id=uuid.uuid4(), edge_code="E1", street_name="S1", from_node_id=node1.node_id, to_node_id=node2.node_id, length_km=1.0, max_speed_limit=60)

    mock_session.exec.side_effect = [
        MagicMock(all=lambda: [node1, node2]),
        MagicMock(all=lambda: [edge]),
        MagicMock(all=lambda: [node1, node2]),
        MagicMock(all=lambda: [edge]),
    ]

    g1 = build_graph(mock_session, weight_mode="distance")
    g2 = build_graph(mock_session, weight_mode="distance", force_refresh=True)
    assert g1 is not g2
    assert mock_session.exec.call_count == 4

