import unittest
import uuid
from datetime import UTC, datetime

class TestSchemasEdgeStatus(unittest.TestCase):
    def test_node_brief_and_edge_status_models(self):
        from app.schemas.edge_status import EdgeStatusItem, EdgeStatusResponse, NodeBrief

        node_from = NodeBrief(
            node_code="NODE_1",
            node_name="Node 1",
            district="Đống Đa",
            lat=21.01,
            lng=105.82,
        )
        node_to = NodeBrief(
            node_code="NODE_2",
            node_name="Node 2",
            district="Cầu Giấy",
            lat=21.03,
            lng=105.80,
        )
        edge_id = uuid.uuid4()
        now = datetime.now(UTC)

        item = EdgeStatusItem(
            edge_id=edge_id,
            edge_code="EDGE_01",
            street_name="Đường Láng",
            length_km=4.1,
            max_speed_limit=50,
            from_node=node_from,
            to_node=node_to,
            speed=35.5,
            congestion_level=1,
            congestion_text="Thông thoáng",
            updated_at=now,
        )

        self.assertEqual(item.edge_code, "EDGE_01")
        self.assertEqual(item.congestion_text, "Thông thoáng")
        self.assertEqual(item.from_node.district, "Đống Đa")

        resp = EdgeStatusResponse(
            total=1,
            updated_at=now,
            filters={"district": "Đống Đa"},
            edges=[item],
        )
        self.assertEqual(resp.total, 1)
        self.assertEqual(len(resp.edges), 1)
        self.assertEqual(resp.filters["district"], "Đống Đa")

    def test_parse_bbox_param_from_discrete_coords(self):
        from app.schemas.edge_status import parse_bbox_param

        min_lat, min_lng, max_lat, max_lng = parse_bbox_param(
            bbox=None, min_lat=20.99, min_lng=105.80, max_lat=21.05, max_lng=105.85
        )
        self.assertEqual(min_lat, 20.99)
        self.assertEqual(min_lng, 105.80)
        self.assertEqual(max_lat, 21.05)
        self.assertEqual(max_lng, 105.85)

    def test_parse_bbox_param_from_string(self):
        from app.schemas.edge_status import parse_bbox_param

        # Standard GIS bbox: min_lng,min_lat,max_lng,max_lat
        min_lat, min_lng, max_lat, max_lng = parse_bbox_param(
            bbox="105.80,20.99,105.85,21.05"
        )
        self.assertEqual(min_lat, 20.99)
        self.assertEqual(min_lng, 105.80)
        self.assertEqual(max_lat, 21.05)
        self.assertEqual(max_lng, 105.85)

        # Alternative format: min_lat,min_lng,max_lat,max_lng
        min_lat2, min_lng2, max_lat2, max_lng2 = parse_bbox_param(
            bbox="20.99,105.80,21.05,105.85"
        )
        self.assertEqual(min_lat2, 20.99)
        self.assertEqual(min_lng2, 105.80)
        self.assertEqual(max_lat2, 21.05)
        self.assertEqual(max_lng2, 105.85)

    def test_parse_bbox_param_invalid_range(self):
        from app.schemas.edge_status import parse_bbox_param

        with self.assertRaises(ValueError):
            parse_bbox_param(min_lat=21.10, max_lat=21.00)

        with self.assertRaises(ValueError):
            parse_bbox_param(min_lng=106.0, max_lng=105.0)

        with self.assertRaises(ValueError):
            parse_bbox_param(bbox="invalid,bbox,format")

        # Range boundaries [-90, 90] and [-180, 180]
        with self.assertRaises(ValueError):
            parse_bbox_param(min_lat=-95.0)

        with self.assertRaises(ValueError):
            parse_bbox_param(max_lat=95.0)

        with self.assertRaises(ValueError):
            parse_bbox_param(min_lng=-185.0)

        with self.assertRaises(ValueError):
            parse_bbox_param(max_lng=185.0)

    def test_parse_bbox_standard_gis_order(self):
        from app.schemas.edge_status import parse_bbox_param

        # When coordinates are both <= 90, default canonical order is min_lng, min_lat, max_lng, max_lat
        min_lat, min_lng, max_lat, max_lng = parse_bbox_param(bbox="10.0,20.0,15.0,25.0")
        self.assertEqual(min_lng, 10.0)
        self.assertEqual(min_lat, 20.0)
        self.assertEqual(max_lng, 15.0)
        self.assertEqual(max_lat, 25.0)


if __name__ == "__main__":
    unittest.main()
