from pydantic import BaseModel, ConfigDict, Field


class GeocodeQuery(BaseModel):
    """Tham số truy vấn tìm kiếm địa điểm (gợi ý khi gõ)."""

    q: str = Field(
        min_length=3,
        max_length=200,
        description="Từ khóa địa điểm, tối thiểu 3 ký tự",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Số gợi ý tối đa trả về (1-10)",
    )
    viewbox: str | None = Field(
        default=None,
        pattern=r"^-?\d+(\.\d+)?,-?\d+(\.\d+)?,-?\d+(\.\d+)?,-?\d+(\.\d+)?$",
        description="Giới hạn kết quả trong khung bbox: lon1,lat1,lon2,lat2",
    )


class GeocodeResult(BaseModel):
    """Một gợi ý địa điểm trả về từ Nominatim."""

    model_config = ConfigDict(frozen=True)

    place_id: int
    display_name: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    type: str | None = None
    category: str | None = None
    importance: float | None = Field(default=None, ge=0, le=1)


class ReverseGeocodeQuery(BaseModel):
    """Tham số tra cứu ngược từ tọa độ (dùng khi chọn điểm trên bản đồ)."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
