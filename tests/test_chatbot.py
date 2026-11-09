from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.config import settings
from app.core.database import get_session
from app.main import app
from app.models.edge import Edge
from app.models.node import Node


def test_chatbot_without_api_key_and_with_mock_tools():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with Session(engine) as session:
        node1 = Node(
            node_code="NODE_1",
            node_name="Ngã tư Sở",
            district="Đống Đa",
            latitude=21.002,
            longitude=105.819,
        )
        node2 = Node(
            node_code="NODE_2",
            node_name="Cầu Giấy",
            district="Cầu Giấy",
            latitude=21.033,
            longitude=105.798,
        )
        session.add_all([node1, node2])
        session.commit()
        session.refresh(node1)
        session.refresh(node2)

        edge = Edge(
            edge_code="EDGE_LANG",
            street_name="Đường Láng",
            from_node_id=node1.node_id,
            to_node_id=node2.node_id,
            length_km=4.0,
            max_speed_limit=50,
        )
        session.add(edge)
        session.commit()

    with TestClient(app) as client:
        # 1. Without GEMINI_API_KEY -> Smart Heuristic Assistant fallback
        settings.GEMINI_API_KEY = None
        res_fallback = client.post(
            "/api/v1/chatbot/chat",
            json={"message": "Đường Láng lúc 18h có tắc không?"},
        )
        assert res_fallback.status_code == 200
        data_fb = res_fallback.json()["data"]
        assert "reply" in data_fb
        assert len(data_fb["reply"]) > 0

        # 2. Mocked Gemini client tool calling
        settings.GEMINI_API_KEY = "dummy-test-key"

        mock_tool_call = MagicMock()
        mock_tool_call.name = "get_traffic_forecast"
        mock_tool_call.args = {"street_name": "Đường Láng", "hour_of_day": 18}

        mock_candidate = MagicMock()
        mock_part = MagicMock()
        mock_part.function_call = mock_tool_call
        mock_part.text = None
        mock_candidate.content.parts = [mock_part]

        mock_final_part = MagicMock()
        mock_final_part.function_call = None
        mock_final_part.text = "Chào bạn, Đường Láng lúc 18h dự báo sẽ ùn tắc nhẹ."
        mock_final_candidate = MagicMock()
        mock_final_candidate.content.parts = [mock_final_part]

        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.side_effect = [
            MagicMock(candidates=[mock_candidate]),
            MagicMock(candidates=[mock_final_candidate]),
        ]

        with patch(
            "app.services.chatbot_service.ChatbotService._get_client",
            return_value=mock_client_instance,
        ):
            res_mock = client.post(
                "/api/v1/chatbot/chat",
                json={"message": "Kiểm tra dự báo Đường Láng 18h"},
            )
            assert res_mock.status_code == 200
            data_mock = res_mock.json()["data"]
            assert "ùn tắc" in data_mock["reply"]

    app.dependency_overrides.clear()
