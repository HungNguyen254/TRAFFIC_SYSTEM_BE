import csv
import logging
import unicodedata
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from app.models.edge import Edge

logger = logging.getLogger(__name__)

def strip_accents(value: str) -> str:
    """Bỏ dấu tiếng Việt + lowercase: 'Đường Láng' -> 'duong lang'."""
    normalized = unicodedata.normalize("NFD", value)
    without_marks = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return without_marks.replace("đ", "d").replace("Đ", "d").lower()


DATA_DIR = Path("data")
SYNTHETIC_CSV = DATA_DIR / "synthetic_traffic_dataset.csv"


def _speed_to_congestion_level(speed_kmh: float) -> int:
    """Đổi tốc độ trung bình thành mức ùn tắc 1..4 (khớp legend trên FE)."""
    if speed_kmh >= 35.0:
        return 1  # Thông thoáng
    if speed_kmh >= 25.0:
        return 2  # Di chuyển chậm
    if speed_kmh >= 15.0:
        return 3  # Ùn tắc nghiêm trọng
    return 4  # Kẹt xe hoàn toàn


@lru_cache(maxsize=1)
def _load_traffic_csv() -> dict[str, list[tuple[int, int, float]]]:
    """Đọc dataset CSV 1 lần và nhóm theo edge_code.

    Trả về: { edge_code: [(hour_of_day, day_of_week, average_speed), ...] }
    """
    by_edge: dict[str, list[tuple[int, int, float]]] = {}
    if not SYNTHETIC_CSV.exists():
        logger.warning("Không tìm thấy file %s - bản đồ sẽ dùng tốc độ mặc định.", SYNTHETIC_CSV)
        return by_edge

    try:
        with SYNTHETIC_CSV.open(mode="r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = (row.get("edge_code") or "").strip()
                speed_raw = (row.get("average_speed") or "").strip()
                if not code or not speed_raw:
                    continue
                try:
                    hour = int(row["hour_of_day"])
                    dow = int(row["day_of_week"])
                    speed = float(speed_raw)
                except (KeyError, ValueError):
                    continue
                by_edge.setdefault(code, []).append((hour, dow, speed))
        logger.info("Đã nạp %d edge từ dataset CSV %s", len(by_edge), SYNTHETIC_CSV.name)
    except OSError as exc:
        logger.error("Lỗi đọc dataset CSV %s: %s", SYNTHETIC_CSV, exc)
    return by_edge


def _averages_by_hour(records: list[tuple[int, int, float]]) -> dict[int, float]:
    """Trung bình tốc độ theo từng giờ (gộp cả thứ trong tuần)."""
    sums: dict[int, tuple[float, int]] = {}
    for hour, _dow, speed in records:
        total, count = sums.get(hour, (0.0, 0))
        sums[hour] = (total + speed, count + 1)
    return {hour: total / count for hour, (total, count) in sums.items()}


class TrafficService:
    """Truy vấn dữ liệu lưới đường (nodes/edges) + dataset CSV."""

    @staticmethod
    def get_edges_by_street(session: Session, street_name: str) -> list[Edge]:
        """Tìm các đoạn đường khớp tên (không phân biệt hoa thường/thanh điệu, khớp một phần).

        Ưu tiên: ilike chính xác trên DB -> nếu rỗng thì fallback so sánh bỏ dấu
        (cho phép người dùng gõ "Kim Ma", "Nguyen Trai"... vẫn tìm được).
        """
        query = select(Edge).where(Edge.street_name.ilike(f"%{street_name.strip()}%"))
        edges = list(session.exec(query).all())
        if edges:
            return edges

        target = strip_accents(street_name.strip())
        if not target:
            return []
        return [
            edge
            for edge in session.exec(select(Edge)).all()
            if target in strip_accents(edge.street_name or "")
        ]

    @staticmethod
    def get_edge_by_id(session: Session, edge_id: uuid.UUID) -> Optional[Edge]:
        return session.get(Edge, edge_id)

    @staticmethod
    def get_all_edges(session: Session) -> list[Edge]:
        return list(session.exec(select(Edge)).all())

    @classmethod
    def get_edge_traffic_snapshot(cls, edge: Edge, hour_of_day: int, day_of_week: int) -> dict:
        """Tốc độ hiện tại của 1 edge, tính từ dataset CSV lịch sử.

        Ưu tiên đúng (hour, day_of_week); nếu thiếu thì gộp theo giờ.
        Day_of_week dùng quy ước của dataset generate_synthetic_traffic.py:
        0 = thứ 2 ... 6 = chủ nhật (giống weekday() của Python).
        """
        default_speed = float(edge.max_speed_limit) * 0.7
        records = _load_traffic_csv().get(edge.edge_code, [])

        exact = [s for h, d, s in records if h == hour_of_day and d == day_of_week]
        pool = exact or [s for h, _d, s in records if h == hour_of_day]
        if not pool:
            return {"speed": round(default_speed, 1), "congestion_level": _speed_to_congestion_level(default_speed)}

        speed = sum(pool) / len(pool)
        return {
            "speed": round(speed, 1),
            "congestion_level": _speed_to_congestion_level(speed),
        }

    @classmethod
    def get_edges_with_traffic(
        cls, session: Session, hour_of_day: int, day_of_week: int
    ) -> dict:
        """Trả về payload cho GET /edges: danh sách nodes + edges kèm màu giao thông.

        Màu được tính từ average_speed trong CSV (lọc theo giờ hiện tại),
        khớp 4 mức legend: 1 xanh (>35), 2 vàng (25-35), 3 đỏ (15-25), 4 đỏ đậm (<15).
        """
        from app.models.node import Node

        nodes = list(session.exec(select(Node)).all())
        edges = cls.get_all_edges(session)
        node_by_id = {n.node_id: n for n in nodes}

        node_payload = [
            {
                "node_id": str(n.node_id),
                "node_code": n.node_code,
                "node_name": n.node_name,
                "district": n.district,
                "lat": n.latitude,
                "lng": n.longitude,
            }
            for n in nodes
        ]
        edge_payload = []
        for e in edges:
            from_node = node_by_id.get(e.from_node_id)
            to_node = node_by_id.get(e.to_node_id)
            snapshot = cls.get_edge_traffic_snapshot(e, hour_of_day, day_of_week)
            edge_payload.append(
                {
                    "edge_id": str(e.edge_id),
                    "edge_code": e.edge_code,
                    "street_name": e.street_name,
                    "length_km": e.length_km,
                    "max_speed_limit": e.max_speed_limit,
                    "from": {
                        "node_code": from_node.node_code if from_node else None,
                        "node_name": from_node.node_name if from_node else None,
                        "lat": from_node.latitude if from_node else None,
                        "lng": from_node.longitude if from_node else None,
                    },
                    "to": {
                        "node_code": to_node.node_code if to_node else None,
                        "node_name": to_node.node_name if to_node else None,
                        "lat": to_node.latitude if to_node else None,
                        "lng": to_node.longitude if to_node else None,
                    },
                    "congestion_level": snapshot["congestion_level"],
                    "speed": snapshot["speed"],
                }
            )
        return {"nodes": node_payload, "edges": edge_payload}
