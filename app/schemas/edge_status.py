import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NodeBrief(BaseModel):
    node_code: str
    node_name: str
    district: str | None = None
    lat: float
    lng: float


class EdgeStatusItem(BaseModel):
    edge_id: uuid.UUID
    edge_code: str
    street_name: str
    length_km: float
    max_speed_limit: int
    from_node: NodeBrief | None = None
    to_node: NodeBrief | None = None
    speed: float
    congestion_level: int = Field(
        ge=1, le=4, description="1: Thông thoáng, 2: Di chuyển chậm, 3: Ùn tắc nghiêm trọng, 4: Kẹt xe hoàn toàn"
    )
    congestion_text: str
    updated_at: datetime


class EdgeStatusResponse(BaseModel):
    total: int
    updated_at: datetime
    filters: dict[str, Any] = Field(default_factory=dict)
    edges: list[EdgeStatusItem]


def parse_bbox_param(
    bbox: str | None = None,
    min_lat: float | None = None,
    min_lng: float | None = None,
    max_lat: float | None = None,
    max_lng: float | None = None,
) -> tuple[float | None, float | None, float | None, float | None]:
    """Parse và validate tham số bounding box.

    Hỗ trợ:
    1. 4 tham số rời: min_lat, min_lng, max_lat, max_lng
    2. Chuỗi bbox: "min_lng,min_lat,max_lng,max_lat" (chuẩn GIS) hoặc "min_lat,min_lng,max_lat,max_lng"
    """
    if bbox:
        parts = [p.strip() for p in bbox.split(",")]
        if len(parts) != 4:
            raise ValueError("Tham số bbox không đúng định dạng. Yêu cầu 4 giá trị số phân tách bằng dấu phẩy.")
        try:
            val1, val2, val3, val4 = (float(p) for p in parts)
        except ValueError as exc:
            raise ValueError("Tham số bbox chứa giá trị không phải số hợp lệ.") from exc

        # Tự động nhận diện thứ tự:
        # Nếu val1 > val2 (ví dụ kinh độ Hà Nội ~105.8 > vĩ độ ~21.0), đây là định dạng min_lng,min_lat,max_lng,max_lat
        if val1 > val2:
            min_lng, min_lat, max_lng, max_lat = val1, val2, val3, val4
        else:
            min_lat, min_lng, max_lat, max_lng = val1, val2, val3, val4

    # Kiểm tra hợp lệ nếu có cả min và max
    if min_lat is not None and max_lat is not None and min_lat > max_lat:
        raise ValueError(f"min_lat ({min_lat}) không được lớn hơn max_lat ({max_lat}).")

    if min_lng is not None and max_lng is not None and min_lng > max_lng:
        raise ValueError(f"min_lng ({min_lng}) không được lớn hơn max_lng ({max_lng}).")

    return min_lat, min_lng, max_lat, max_lng
