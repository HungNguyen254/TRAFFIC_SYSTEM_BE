import uuid

from fastapi import APIRouter, Query, Request, status

from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response
from app.schemas.geocoding import GeocodeResult
from app.services import geocoding_service

router = APIRouter(prefix="/geocode", tags=["geocoding"])


@router.get(
    "/search",
    response_model=StandardResponse[list[GeocodeResult]],
    status_code=status.HTTP_200_OK,
    summary="Gợi ý địa điểm khi gõ (Nominatim)",
    description=(
        "Tìm địa điểm theo từ khóa, dùng cho autocomplete khi người dùng "
        "nhập điểm đi / điểm đến. Hỗ trợ giới hạn kết quả trong khung nhìn "
        "bản đồ qua tham số viewbox (lon1,lat1,lon2,lat2)."
    ),
)
@limiter.limit("10/minute")
def search_places(
    request: Request,
    q: str = Query(
        min_length=3,
        max_length=200,
        description="Từ khóa địa điểm, tối thiểu 3 ký tự",
    ),  # noqa: B008
    limit: int = Query(
        default=5,
        ge=1,
        le=10,
        description="Số gợi ý tối đa (1-10)",
    ),  # noqa: B008
    viewbox: str | None = Query(
        default=None,
        pattern=r"^-?\d+(\.\d+)?,-?\d+(\.\d+)?,-?\d+(\.\d+)?,-?\d+(\.\d+)?$",
        description="Giới hạn kết quả trong bbox: lon1,lat1,lon2,lat2",
    ),  # noqa: B008
):
    """Gợi ý địa điểm theo từ khóa, dữ liệu lấy từ Nominatim."""
    results = geocoding_service.search_places(q=q, limit=limit, viewbox=viewbox)
    return success_response(
        request=request,
        message="Tìm địa điểm thành công",
        data=results,
    )


@router.get(
    "/reverse",
    response_model=StandardResponse[GeocodeResult],
    status_code=status.HTTP_200_OK,
    summary="Tra cứu địa điểm từ tọa độ (khi chọn điểm trên bản đồ)",
    description=(
        "Nhận tọa độ đã được validate (lat ∈ [-90, 90], lon ∈ [-180, 180]) "
        "và trả về tên địa điểm tương ứng, dùng khi người dùng đặt marker "
        "điểm đi / điểm đến trực tiếp trên bản đồ."
    ),
)
@limiter.limit("10/minute")
def reverse_geocode(
    request: Request,
    lat: float = Query(ge=-90, le=90, description="Vĩ độ"),  # noqa: B008
    lon: float = Query(ge=-180, le=180, description="Kinh độ"),  # noqa: B008
):
    """Trả về địa điểm tại tọa độ lat/lon."""
    result = geocoding_service.reverse_geocode(lat=lat, lon=lon)
    return success_response(
        request=request,
        message="Tra cứu địa điểm thành công",
        data=result,
    )
