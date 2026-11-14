import logging
import threading
import unicodedata
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.core.database import engine
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.edge import Edge
from app.models.node import Node
from app.models.traffic_data import TrafficData
from app.schemas.edge_status import EdgeStatusItem, EdgeStatusResponse, NodeBrief
from app.schemas.traffic import EdgeCreate, EdgeUpdate

logger = logging.getLogger(__name__)
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

_TRAFFIC_DATA_CACHE: dict[str, list[tuple[int, int, float]]] | None = None
_TRAFFIC_DATA_LOCK = threading.Lock()


def clear_traffic_data_cache() -> None:
    """Xóa cache dữ liệu giao thông trong bộ nhớ để làm mới từ database."""
    global _TRAFFIC_DATA_CACHE
    with _TRAFFIC_DATA_LOCK:
        _TRAFFIC_DATA_CACHE = None


def _load_traffic_data_from_db(
    session: Session | None = None,
) -> dict[str, list[tuple[int, int, float]]]:
    """Đọc dữ liệu lịch sử từ bảng database traffic_data và nhóm theo edge_code.

    Trả về: { edge_code: [(hour_of_day, day_of_week, average_speed), ...] }
    """
    global _TRAFFIC_DATA_CACHE
    if _TRAFFIC_DATA_CACHE is not None:
        return _TRAFFIC_DATA_CACHE

    with _TRAFFIC_DATA_LOCK:
        if _TRAFFIC_DATA_CACHE is not None:
            return _TRAFFIC_DATA_CACHE

        owns_session = session is None
        db_session = Session(engine) if owns_session else session
        by_edge: dict[str, list[tuple[int, int, float]]] = {}
        try:
            query = select(
                TrafficData.edge_code,
                TrafficData.hour_of_day,
                TrafficData.day_of_week,
                TrafficData.average_speed,
            )
            rows = db_session.exec(query).all()
            for edge_code, hour, dow, speed in rows:
                code = (edge_code or "").strip()
                if code:
                    by_edge.setdefault(code, []).append((int(hour), int(dow), float(speed)))
            _TRAFFIC_DATA_CACHE = by_edge
            logger.info("Đã nạp %d edge từ bảng database traffic_data", len(by_edge))
        except Exception as exc:  # noqa: BLE001
            logger.error("Lỗi đọc dữ liệu từ bảng traffic_data: %s", exc)
        finally:
            if owns_session:
                db_session.close()

        return _TRAFFIC_DATA_CACHE if _TRAFFIC_DATA_CACHE is not None else {}


def strip_accents(value: str) -> str:
    """Bỏ dấu tiếng Việt + lowercase: 'Đường Láng' -> 'duong lang'."""
    normalized = unicodedata.normalize("NFD", value)
    without_marks = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return without_marks.replace("đ", "d").replace("Đ", "d").lower()


def _speed_to_congestion_level(speed_kmh: float) -> int:
    """Đổi tốc độ trung bình thành mức ùn tắc 1..4 (khớp legend trên FE)."""
    if speed_kmh >= 35.0:
        return 1  # Thông thoáng
    if speed_kmh >= 25.0:
        return 2  # Di chuyển chậm
    if speed_kmh >= 15.0:
        return 3  # Ùn tắc nghiêm trọng
    return 4  # Kẹt xe hoàn toàn


def _congestion_level_to_text(level: int) -> str:
    """Đổi mã mức độ ùn tắc 1..4 thành nhãn văn bản mô tả."""
    mapping = {
        1: "Thông thoáng",
        2: "Di chuyển chậm",
        3: "Ùn tắc nghiêm trọng",
        4: "Kẹt xe hoàn toàn",
    }
    return mapping.get(level, "Không xác định")


def _is_node_in_bbox(
    node: Any,
    min_lat: float | None,
    min_lng: float | None,
    max_lat: float | None,
    max_lng: float | None,
) -> bool:
    if node is None:
        return False
    if min_lat is not None and node.latitude < min_lat:
        return False
    if max_lat is not None and node.latitude > max_lat:
        return False
    if min_lng is not None and node.longitude < min_lng:
        return False
    if max_lng is not None and node.longitude > max_lng:
        return False
    return True


def _is_edge_in_bbox(
    from_node: Any,
    to_node: Any,
    min_lat: float | None,
    min_lng: float | None,
    max_lat: float | None,
    max_lng: float | None,
) -> bool:
    if min_lat is None and min_lng is None and max_lat is None and max_lng is None:
        return True
    from_inside = _is_node_in_bbox(from_node, min_lat, min_lng, max_lat, max_lng)
    to_inside = _is_node_in_bbox(to_node, min_lat, min_lng, max_lat, max_lng)
    if from_inside or to_inside:
        return True

    if from_node is None or to_node is None:
        return False

    edge_min_lat = min(from_node.latitude, to_node.latitude)
    edge_max_lat = max(from_node.latitude, to_node.latitude)
    edge_min_lng = min(from_node.longitude, to_node.longitude)
    edge_max_lng = max(from_node.longitude, to_node.longitude)

    b_min_lat = min_lat if min_lat is not None else -90.0
    b_max_lat = max_lat if max_lat is not None else 90.0
    b_min_lng = min_lng if min_lng is not None else -180.0
    b_max_lng = max_lng if max_lng is not None else 180.0

    if (
        edge_max_lat < b_min_lat
        or edge_min_lat > b_max_lat
        or edge_max_lng < b_min_lng
        or edge_min_lng > b_max_lng
    ):
        return False

    return True


def _is_edge_in_district(from_node: Any, to_node: Any, district: str | None) -> bool:
    if not district or not district.strip():
        return True
    target = strip_accents(district.strip())
    from_dist = strip_accents(from_node.district or "") if from_node else ""
    to_dist = strip_accents(to_node.district or "") if to_node else ""
    return target in from_dist or target in to_dist


class TrafficService:
    """Truy vấn dữ liệu lưới đường (nodes/edges) + dữ liệu traffic từ database."""

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
    def get_edge_by_id(session: Session, edge_id: uuid.UUID) -> Edge | None:
        return session.get(Edge, edge_id)

    @staticmethod
    def get_all_edges(session: Session) -> list[Edge]:
        return list(session.exec(select(Edge)).all())

    @classmethod
    def list_edges(cls, session: Session, street_name: str | None = None) -> list[Edge]:
        """Danh sách đoạn đường; lọc theo tên đường nếu có tham số."""
        if street_name and street_name.strip():
            return cls.get_edges_by_street(session, street_name)
        return cls.get_all_edges(session)

    @staticmethod
    def _ensure_edge_code_available(
        session: Session, edge_code: str, exclude_edge_id: uuid.UUID | None = None
    ) -> None:
        """Chặn trùng edge_code trước khi ghi DB để trả lỗi rõ ràng thay vì IntegrityError."""
        query = select(Edge).where(Edge.edge_code == edge_code)
        if exclude_edge_id is not None:
            query = query.where(Edge.edge_id != exclude_edge_id)
        if session.exec(query).first():
            raise BadRequestException(
                message=f"Mã đoạn đường '{edge_code}' đã tồn tại.",
                error_code="EDGE_CODE_DUPLICATED",
                details={"edge_code": edge_code},
            )

    @staticmethod
    def _validate_edge_nodes(
        session: Session,
        from_node_id: uuid.UUID,
        to_node_id: uuid.UUID,
    ) -> None:
        """Kiểm tra 2 nút giao tồn tại và không trùng nhau."""
        if from_node_id == to_node_id:
            raise BadRequestException(
                message="Nút đầu và nút cuối của đoạn đường phải khác nhau.",
                error_code="EDGE_SAME_NODE",
            )
        missing = [
            str(node_id)
            for node_id in (from_node_id, to_node_id)
            if session.get(Node, node_id) is None
        ]
        if missing:
            raise NotFoundException(
                message=f"Không tìm thấy nút giao: {', '.join(missing)}",
                error_code="NODE_NOT_FOUND",
                details={"node_ids": missing},
            )

    @classmethod
    def create_edge(cls, session: Session, payload: EdgeCreate) -> Edge:
        """Tạo mới một đoạn đường."""
        cls._ensure_edge_code_available(session, payload.edge_code)
        cls._validate_edge_nodes(session, payload.from_node_id, payload.to_node_id)

        edge = Edge(**payload.model_dump())
        session.add(edge)
        session.commit()
        session.refresh(edge)
        return edge

    @classmethod
    def update_edge(
        cls, session: Session, edge_id: uuid.UUID, payload: EdgeUpdate
    ) -> Edge:
        """Cập nhật thông tin đoạn đường (chỉ các trường được gửi lên)."""
        edge = cls.get_edge_by_id(session, edge_id)
        if edge is None:
            raise NotFoundException(
                message=f"Không tìm thấy đoạn đường có id {edge_id}.",
                error_code="EDGE_NOT_FOUND",
                details={"edge_id": str(edge_id)},
            )

        updates = payload.model_dump(exclude_unset=True)
        for field_name, value in updates.items():
            # geom được phép set null, các cột còn lại là NOT NULL.
            if value is None and field_name != "geom":
                raise BadRequestException(
                    message=f"Trường '{field_name}' không được để trống.",
                    error_code="EDGE_FIELD_REQUIRED",
                    details={"field": field_name},
                )

        new_edge_code = updates.get("edge_code")
        if new_edge_code is not None:
            cls._ensure_edge_code_available(session, new_edge_code, exclude_edge_id=edge_id)

        from_node_id = updates.get("from_node_id", edge.from_node_id)
        to_node_id = updates.get("to_node_id", edge.to_node_id)
        if "from_node_id" in updates or "to_node_id" in updates:
            cls._validate_edge_nodes(session, from_node_id, to_node_id)

        for field_name, value in updates.items():
            setattr(edge, field_name, value)

        session.add(edge)
        session.commit()
        session.refresh(edge)
        return edge

    @classmethod
    def delete_edge(cls, session: Session, edge_id: uuid.UUID) -> None:
        """Xoá một đoạn đường."""
        edge = cls.get_edge_by_id(session, edge_id)
        if edge is None:
            raise NotFoundException(
                message=f"Không tìm thấy đoạn đường có id {edge_id}.",
                error_code="EDGE_NOT_FOUND",
                details={"edge_id": str(edge_id)},
            )

        session.delete(edge)
        session.commit()

    @classmethod
    def get_edge_traffic_snapshot(
        cls,
        edge: Edge,
        hour_of_day: int,
        day_of_week: int,
        session: Session | None = None,
    ) -> dict:
        """Tốc độ hiện tại của 1 edge, tính từ bảng database traffic_data.

        Ưu tiên đúng (hour, day_of_week); nếu thiếu thì gộp theo giờ.
        Day_of_week: 0 = thứ 2 ... 6 = chủ nhật.
        """
        default_speed = float(edge.max_speed_limit) * 0.7
        records = _load_traffic_data_from_db(session).get(edge.edge_code, [])

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
    def get_edges_status(
        cls,
        session: Session,
        min_lat: float | None = None,
        min_lng: float | None = None,
        max_lat: float | None = None,
        max_lng: float | None = None,
        district: str | None = None,
        hour_of_day: int | None = None,
        day_of_week: int | None = None,
    ) -> EdgeStatusResponse:
        """Lấy danh sách đoạn đường kèm trạng thái giao thông mới nhất,

        lọc theo khung bản đồ (bounding box) hoặc theo khu vực (district/area).
        """
        now_utc = datetime.now(UTC)
        now_local = datetime.now(LOCAL_TZ)
        h = hour_of_day if hour_of_day is not None else now_local.hour
        d = day_of_week if day_of_week is not None else now_local.weekday()

        nodes = list(session.exec(select(Node)).all())
        edges = cls.get_all_edges(session)
        node_by_id = {n.node_id: n for n in nodes}

        filtered_items: list[EdgeStatusItem] = []
        for e in edges:
            from_node = node_by_id.get(e.from_node_id)
            to_node = node_by_id.get(e.to_node_id)

            if not _is_edge_in_bbox(from_node, to_node, min_lat, min_lng, max_lat, max_lng):
                continue

            if not _is_edge_in_district(from_node, to_node, district):
                continue

            snapshot = cls.get_edge_traffic_snapshot(e, h, d, session=session)
            congestion_level = snapshot["congestion_level"]

            node_from_brief = (
                NodeBrief(
                    node_code=from_node.node_code,
                    node_name=from_node.node_name,
                    district=from_node.district,
                    lat=from_node.latitude,
                    lng=from_node.longitude,
                )
                if from_node
                else None
            )

            node_to_brief = (
                NodeBrief(
                    node_code=to_node.node_code,
                    node_name=to_node.node_name,
                    district=to_node.district,
                    lat=to_node.latitude,
                    lng=to_node.longitude,
                )
                if to_node
                else None
            )

            filtered_items.append(
                EdgeStatusItem(
                    edge_id=e.edge_id,
                    edge_code=e.edge_code,
                    street_name=e.street_name,
                    length_km=e.length_km,
                    max_speed_limit=e.max_speed_limit,
                    from_node=node_from_brief,
                    to_node=node_to_brief,
                    speed=snapshot["speed"],
                    congestion_level=congestion_level,
                    congestion_text=_congestion_level_to_text(congestion_level),
                    updated_at=now_utc,
                )
            )

        filters = {
            "min_lat": min_lat,
            "min_lng": min_lng,
            "max_lat": max_lat,
            "max_lng": max_lng,
            "district": district,
            "hour": h,
            "day_of_week": d,
        }

        return EdgeStatusResponse(
            total=len(filtered_items),
            updated_at=now_utc,
            filters={k: v for k, v in filters.items() if v is not None},
            edges=filtered_items,
        )

    @classmethod
    def get_edges_with_traffic(
        cls,
        session: Session,
        hour_of_day: int,
        day_of_week: int,
        min_lat: float | None = None,
        min_lng: float | None = None,
        max_lat: float | None = None,
        max_lng: float | None = None,
        district: str | None = None,
    ) -> dict:
        """Trả về payload cho GET /edges: danh sách nodes + edges kèm màu giao thông.

        Hỗ trợ lọc theo bbox và district nếu được cung cấp.
        Bổ sung timestamp updated_at.
        """
        now_utc = datetime.now(UTC)
        nodes = list(session.exec(select(Node)).all())
        edges = cls.get_all_edges(session)
        node_by_id = {n.node_id: n for n in nodes}

        edge_payload = []
        matched_node_ids = set()

        for e in edges:
            from_node = node_by_id.get(e.from_node_id)
            to_node = node_by_id.get(e.to_node_id)

            if not _is_edge_in_bbox(from_node, to_node, min_lat, min_lng, max_lat, max_lng):
                continue

            if not _is_edge_in_district(from_node, to_node, district):
                continue

            snapshot = cls.get_edge_traffic_snapshot(e, hour_of_day, day_of_week, session=session)
            if from_node:
                matched_node_ids.add(from_node.node_id)
            if to_node:
                matched_node_ids.add(to_node.node_id)

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
                    "updated_at": now_utc.isoformat(),
                }
            )

        has_filter = any(
            param is not None
            for param in (min_lat, min_lng, max_lat, max_lng, district)
        )
        filtered_nodes = (
            [n for n in nodes if n.node_id in matched_node_ids]
            if has_filter
            else nodes
        )

        node_payload = [
            {
                "node_id": str(n.node_id),
                "node_code": n.node_code,
                "node_name": n.node_name,
                "district": n.district,
                "lat": n.latitude,
                "lng": n.longitude,
            }
            for n in filtered_nodes
        ]
        return {
            "nodes": node_payload,
            "edges": edge_payload,
            "updated_at": now_utc.isoformat(),
        }
