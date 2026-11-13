import unittest
import uuid
from collections.abc import Generator
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.database import get_session
from app.main import app
from app.models.edge import Edge
from app.models.node import Node


class TestApiEdgesStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(cls.engine)

        # Seed sample data
        with Session(cls.engine) as session:
            cls.node_a = Node(
                node_id=uuid.uuid4(),
                node_code="NODE_A",
                node_name="Ngã Tư Sở",
                district="Đống Đa",
                latitude=21.0025,
                longitude=105.8198,
            )
            cls.node_b = Node(
                node_id=uuid.uuid4(),
                node_code="NODE_B",
                node_name="Cầu Giấy",
                district="Cầu Giấy",
                latitude=21.0332,
                longitude=105.7985,
            )
            cls.node_c = Node(
                node_id=uuid.uuid4(),
                node_code="NODE_C",
                node_name="Bạch Mai",
                district="Hai Bà Trưng",
                latitude=20.9980,
                longitude=105.8480,
            )
            session.add_all([cls.node_a, cls.node_b, cls.node_c])
            session.commit()

            cls.edge_1 = Edge(
                edge_id=uuid.uuid4(),
                edge_code="EDGE_LANG",
                street_name="Đường Láng",
                from_node_id=cls.node_a.node_id,
                to_node_id=cls.node_b.node_id,
                length_km=4.1,
                max_speed_limit=50,
            )
            cls.edge_2 = Edge(
                edge_id=uuid.uuid4(),
                edge_code="EDGE_DAICOTVIET",
                street_name="Đường Đại Cồ Việt",
                from_node_id=cls.node_a.node_id,
                to_node_id=cls.node_c.node_id,
                length_km=3.0,
                max_speed_limit=50,
            )
            session.add_all([cls.edge_1, cls.edge_2])
            session.commit()

        def override_get_session() -> Generator[Session]:
            with Session(cls.engine) as s:
                yield s

        app.dependency_overrides[get_session] = override_get_session
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        SQLModel.metadata.drop_all(cls.engine)
        cls.engine.dispose()

    def test_get_edges_status_success(self):
        resp = self.client.get("/api/v1/edges/status")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status_code"], 200)
        self.assertIn("data", body)
        data = body["data"]
        self.assertEqual(data["total"], 2)
        self.assertIn("updated_at", data)
        self.assertEqual(len(data["edges"]), 2)

        edge = data["edges"][0]
        self.assertIn("congestion_level", edge)
        self.assertIn("congestion_text", edge)
        self.assertIn("speed", edge)
        self.assertIn("updated_at", edge)
        self.assertIsNotNone(edge["from_node"])
        self.assertIsNotNone(edge["to_node"])

    def test_get_edges_status_bbox_filter(self):
        # Bbox chỉ bao gồm Node B
        resp = self.client.get(
            "/api/v1/edges/status?min_lat=21.03&max_lat=21.04&min_lng=105.79&max_lng=105.81"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["edges"][0]["edge_code"], "EDGE_LANG")

    def test_get_edges_status_bbox_string_filter(self):
        resp = self.client.get(
            "/api/v1/edges/status?bbox=105.79,21.03,105.81,21.04"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["edges"][0]["edge_code"], "EDGE_LANG")

    def test_get_edges_status_district_and_area_filter(self):
        # Thử district có dấu và không dấu
        resp1 = self.client.get("/api/v1/edges/status?district=Hai Bà Trưng")
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()["data"]
        self.assertEqual(data1["total"], 1)
        self.assertEqual(data1["edges"][0]["edge_code"], "EDGE_DAICOTVIET")

        # Thử param 'area' không dấu
        resp2 = self.client.get("/api/v1/edges/status?area=hai ba trung")
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()["data"]
        self.assertEqual(data2["total"], 1)
        self.assertEqual(data2["edges"][0]["edge_code"], "EDGE_DAICOTVIET")

    def test_get_edges_status_invalid_bbox(self):
        # min_lat > max_lat
        resp = self.client.get("/api/v1/edges/status?min_lat=21.05&max_lat=21.01")
        self.assertEqual(resp.status_code, 400)

        # bbox chuỗi sai
        resp_invalid_str = self.client.get("/api/v1/edges/status?bbox=105.1,abc,xyz")
        self.assertEqual(resp_invalid_str.status_code, 400)

    def test_get_edges_with_filters_backward_compatible(self):
        resp = self.client.get("/api/v1/edges?district=cau giay")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("updated_at", body["data"])
        self.assertEqual(len(body["data"]["edges"]), 1)
        self.assertEqual(body["data"]["edges"][0]["edge_code"], "EDGE_LANG")


if __name__ == "__main__":
    unittest.main()
