import unittest
import uuid
from sqlmodel import Session, SQLModel, create_engine

from app.models.edge import Edge
from app.models.node import Node
from app.services.traffic_service import TrafficService


class TestTrafficServiceStatus(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        # Tạo nodes
        self.node_a = Node(
            node_id=uuid.uuid4(),
            node_code="NODE_A",
            node_name="Ngã Tư Sở",
            district="Đống Đa",
            latitude=21.0025,
            longitude=105.8198,
        )
        self.node_b = Node(
            node_id=uuid.uuid4(),
            node_code="NODE_B",
            node_name="Cầu Giấy",
            district="Cầu Giấy",
            latitude=21.0332,
            longitude=105.7985,
        )
        self.node_c = Node(
            node_id=uuid.uuid4(),
            node_code="NODE_C",
            node_name="Bạch Mai",
            district="Hai Bà Trưng",
            latitude=20.9980,
            longitude=105.8480,
        )
        self.session.add_all([self.node_a, self.node_b, self.node_c])
        self.session.commit()

        # Tạo edges
        self.edge_1 = Edge(
            edge_id=uuid.uuid4(),
            edge_code="EDGE_LANG",
            street_name="Đường Láng",
            from_node_id=self.node_a.node_id,
            to_node_id=self.node_b.node_id,
            length_km=4.1,
            max_speed_limit=50,
        )
        self.edge_2 = Edge(
            edge_id=uuid.uuid4(),
            edge_code="EDGE_DAICOTVIET",
            street_name="Đường Đại Cồ Việt",
            from_node_id=self.node_a.node_id,
            to_node_id=self.node_c.node_id,
            length_km=3.0,
            max_speed_limit=50,
        )
        self.session.add_all([self.edge_1, self.edge_2])
        self.session.commit()

    def tearDown(self):
        self.session.close()
        SQLModel.metadata.drop_all(self.engine)

    def test_get_edges_status_all(self):
        response = TrafficService.get_edges_status(
            self.session, hour_of_day=8, day_of_week=0
        )
        self.assertEqual(response.total, 2)
        self.assertEqual(len(response.edges), 2)
        self.assertIsNotNone(response.updated_at)

        first_edge = response.edges[0]
        self.assertIn(first_edge.congestion_level, [1, 2, 3, 4])
        self.assertIn(first_edge.congestion_text, [
            "Thông thoáng",
            "Di chuyển chậm",
            "Ùn tắc nghiêm trọng",
            "Kẹt xe hoàn toàn",
        ])
        self.assertIsNotNone(first_edge.updated_at)
        self.assertIsNotNone(first_edge.from_node)
        self.assertIsNotNone(first_edge.to_node)

    def test_get_edges_status_bbox_filter(self):
        # Khung chỉ bao gồm Node B (Cầu Giấy: lat 21.0332, lng 105.7985)
        # Node A (21.0025, 105.8198) và Node C (20.9980, 105.8480) nằm ngoài
        response = TrafficService.get_edges_status(
            self.session,
            min_lat=21.03,
            max_lat=21.04,
            min_lng=105.79,
            max_lng=105.81,
            hour_of_day=8,
            day_of_week=0,
        )
        # Edge 1 có điểm to_node là Node B -> nằm trong khung
        # Edge 2 nối Node A và Node C -> không có điểm nào trong khung
        self.assertEqual(response.total, 1)
        self.assertEqual(response.edges[0].edge_code, "EDGE_LANG")

    def test_get_edges_status_district_filter_unaccented(self):
        # Lọc theo 'hai ba trung' không dấu
        response = TrafficService.get_edges_status(
            self.session,
            district="hai ba trung",
            hour_of_day=8,
            day_of_week=0,
        )
        self.assertEqual(response.total, 1)
        self.assertEqual(response.edges[0].edge_code, "EDGE_DAICOTVIET")

        # Lọc theo 'Cau Giay'
        response_cg = TrafficService.get_edges_status(
            self.session,
            district="Cau Giay",
            hour_of_day=8,
            day_of_week=0,
        )
        self.assertEqual(response_cg.total, 1)
        self.assertEqual(response_cg.edges[0].edge_code, "EDGE_LANG")

    def test_get_edges_with_traffic_backward_compatibility(self):
        # Kiểm tra get_edges_with_traffic có thêm trường updated_at và hỗ trợ lọc
        data = TrafficService.get_edges_with_traffic(
            self.session,
            district="hai ba trung",
            hour_of_day=8,
            day_of_week=0,
        )
        self.assertIn("updated_at", data)
        self.assertEqual(len(data["edges"]), 1)
        self.assertEqual(data["edges"][0]["edge_code"], "EDGE_DAICOTVIET")


if __name__ == "__main__":
    unittest.main()
