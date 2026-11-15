"""Service gọi Nominatim (OpenStreetMap) để tìm / tra ngược địa điểm.

Nominatim yêu cầu mọi request phải có User-Agent định danh ứng dụng,
nếu không sẽ bị từ chối (HTTP 403). Ở đây dùng httpx với timeout ngắn,
validate dữ liệu trả về bằng Pydantic trước khi trả cho client.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.schemas.geocoding import GeocodeResult

NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
PHOTON_BASE_URL = "https://photon.komoot.io"
REQUEST_TIMEOUT = 10.0  # giây

_HEADERS = {"User-Agent": f"{settings.APP_NAME}/0.1 (traffic-routing-demo)"}
_PHOTON_HEADERS = {
    "User-Agent": f"{settings.APP_NAME}/0.1 (traffic-routing-demo; Photon fallback)",
    "Accept": "application/json",
}
logger = logging.getLogger(__name__)

# Cache đơn giản trong tiến trình để giảm số call tới Nominatim
# (Nominatim có chính sách giới hạn tối đa 1 request/giây).
_cache: dict[str, list[GeocodeResult]] = {}
_CACHE_MAX_SIZE = 256


def _cache_get(key: str) -> list[GeocodeResult] | None:
    return _cache.get(key)


def _cache_put(key: str, value: list[GeocodeResult]) -> None:
    if len(_cache) >= _CACHE_MAX_SIZE:
        _cache.pop(next(iter(_cache)))  # FIFO eviction
    _cache[key] = value


def _parse_results(payload: object) -> list[GeocodeResult]:
    if not isinstance(payload, list):
        return []
    results: list[GeocodeResult] = []
    for item in payload:
        try:
            results.append(GeocodeResult.model_validate(item))
        except Exception:  # bỏ qua kết quả lỗi định dạng, không chặn cả danh sách
            continue
    return results


def _raise_upstream_error(exc: httpx.HTTPError) -> None:
    if isinstance(exc, httpx.TimeoutException):
        raise BadRequestException(
            message="Dịch vụ bản đồ phản hồi quá chậm, vui lòng thử lại sau!",
            error_code="GEOCODE_TIMEOUT",
        ) from exc
    if isinstance(exc, httpx.ConnectError):
        logger.error("Không thể kết nối Nominatim (%s)", type(exc).__name__)
        raise BadRequestException(
            message=(
                "Backend không kết nối được tới Nominatim. "
                "Kiểm tra kết nối mạng hoặc cấu hình proxy của máy chạy backend."
            ),
            error_code="GEOCODE_CONNECTION_ERROR",
        ) from exc
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        logger.warning("Nominatim trả về HTTP %s", status_code)
        if status_code == 429:
            raise BadRequestException(
                message="Nominatim đang giới hạn yêu cầu. Vui lòng chờ rồi thử lại.",
                error_code="GEOCODE_RATE_LIMITED",
            ) from exc
        if status_code in {401, 403}:
            raise BadRequestException(
                message="Nominatim từ chối yêu cầu. Kiểm tra cấu hình dịch vụ geocoding.",
                error_code="GEOCODE_UPSTREAM_DENIED",
            ) from exc

    logger.error("Yêu cầu Nominatim thất bại (%s)", type(exc).__name__)
    raise BadRequestException(
        message="Không thể truy vấn dịch vụ tìm địa điểm, vui lòng thử lại sau!",
        error_code="GEOCODE_UPSTREAM_ERROR",
    ) from exc


def _photon_display_name(properties: dict[str, object]) -> str:
    parts = (
        properties.get("name"),
        properties.get("housenumber"),
        properties.get("street"),
        properties.get("suburb"),
        properties.get("district"),
        properties.get("city"),
        properties.get("state"),
        properties.get("postcode"),
        properties.get("country"),
    )
    unique_parts: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if isinstance(part, str) and part.strip():
            value = part.strip()
            normalized = value.casefold()
            if normalized not in seen:
                unique_parts.append(value)
                seen.add(normalized)
    return ", ".join(unique_parts)


def _photon_feature_to_result(
    feature: object,
    fallback_coordinates: tuple[float, float] | None = None,
) -> GeocodeResult | None:
    if not isinstance(feature, dict):
        return None
    properties = feature.get("properties")
    geometry = feature.get("geometry")
    if not isinstance(properties, dict) or not isinstance(geometry, dict):
        return None
    coordinates = geometry.get("coordinates")
    if fallback_coordinates is None:
        if (
            not isinstance(coordinates, list)
            or len(coordinates) < 2
        ):
            return None
        lon, lat = coordinates[:2]
    else:
        lat, lon = fallback_coordinates

    try:
        place_id = int(properties.get("osm_id", 0))
        display_name = _photon_display_name(properties)
        if not display_name:
            display_name = f"({float(lat):.5f}, {float(lon):.5f})"
        result = GeocodeResult(
            place_id=place_id,
            display_name=display_name,
            lat=lat,
            lon=lon,
            type=(
                properties.get("osm_value")
                if isinstance(properties.get("osm_value"), str)
                else None
            ),
            category=(
                properties.get("osm_key")
                if isinstance(properties.get("osm_key"), str)
                else None
            ),
        )
    except (TypeError, ValueError):
        return None
    return result


def _photon_request(
    endpoint: str,
    params: dict[str, str],
) -> dict[str, object]:
    try:
        response = httpx.get(
            f"{PHOTON_BASE_URL}/{endpoint}",
            params=params,
            headers=_PHOTON_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Photon fallback request failed (%s)", type(exc).__name__)
        raise BadRequestException(
            message=(
                "Nominatim không kết nối được và dịch vụ dự phòng Photon "
                "cũng không khả dụng. Vui lòng thử lại sau."
            ),
            error_code="GEOCODE_FALLBACK_ERROR",
        ) from exc
    try:
        payload = response.json()
    except ValueError as exc:
        logger.error("Photon fallback returned invalid JSON")
        raise BadRequestException(
            message="Dịch vụ dự phòng Photon trả về dữ liệu không hợp lệ.",
            error_code="GEOCODE_FALLBACK_ERROR",
        ) from exc
    if not isinstance(payload, dict):
        raise BadRequestException(
            message="Dịch vụ dự phòng Photon trả về dữ liệu không hợp lệ.",
            error_code="GEOCODE_FALLBACK_ERROR",
        )
    return payload


def _search_places_photon(
    keyword: str,
    limit: int,
    viewbox: str | None,
) -> list[GeocodeResult]:
    params = {"q": keyword, "limit": str(limit), "lang": "default"}
    if viewbox:
        try:
            west, north, east, south = (float(value) for value in viewbox.split(","))
        except ValueError as exc:
            raise BadRequestException(
                message="Khung tìm kiếm địa điểm không hợp lệ.",
                error_code="GEOCODE_INVALID_VIEWBOX",
            ) from exc
        params["bbox"] = f"{west},{south},{east},{north}"

    payload = _photon_request("api/", params)
    features = payload.get("features")
    if not isinstance(features, list):
        raise BadRequestException(
            message="Dịch vụ dự phòng Photon trả về danh sách không hợp lệ.",
            error_code="GEOCODE_FALLBACK_ERROR",
        )
    results = [
        result
        for feature in features
        if (result := _photon_feature_to_result(feature)) is not None
    ]
    logger.info("Geocoding search completed using Photon fallback")
    return results


def _reverse_geocode_photon(lat: float, lon: float) -> GeocodeResult:
    payload = _photon_request("reverse", {"lat": str(lat), "lon": str(lon)})
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise NotFoundException(
            message="Không tìm thấy địa điểm nào tại tọa độ này!",
            error_code="GEOCODE_NOT_FOUND",
        )
    result = _photon_feature_to_result(features[0], (lat, lon))
    if result is None:
        raise NotFoundException(
            message="Không tìm thấy địa điểm nào tại tọa độ này!",
            error_code="GEOCODE_NOT_FOUND",
        )
    logger.info("Reverse geocoding completed using Photon fallback")
    return result


def search_places(
    q: str,
    limit: int = 5,
    viewbox: str | None = None,
) -> list[GeocodeResult]:
    """Tìm địa điểm theo từ khóa (autocomplete khi người dùng gõ)."""
    keyword = q.strip()
    if len(keyword) < 3:
        raise BadRequestException(message="Từ khóa tìm kiếm phải có ít nhất 3 ký tự!")
    if len(keyword) > 200:
        raise BadRequestException(message="Từ khóa tìm kiếm quá dài (tối đa 200 ký tự)!")

    cache_key = f"search:{keyword.lower()}:{limit}:{viewbox or ''}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params: dict[str, str] = {
        "q": keyword,
        "format": "jsonv2",
        "limit": str(limit),
        "addressdetails": "0",
    }
    if viewbox:
        params["viewbox"] = viewbox
        params["bounded"] = "1"

    try:
        response = httpx.get(
            f"{NOMINATIM_BASE_URL}/search",
            params=params,
            headers=_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except httpx.ConnectError as exc:
        logger.info(
            "Nominatim unavailable; using Photon fallback (%s)",
            type(exc).__name__,
        )
        results = _search_places_photon(keyword, limit, viewbox)
        _cache_put(cache_key, results)
        return results
    except httpx.HTTPError as exc:
        _raise_upstream_error(exc)

    results = _parse_results(response.json())
    _cache_put(cache_key, results)
    return results


def reverse_geocode(lat: float, lon: float) -> GeocodeResult:
    """Tra cứu tên địa điểm từ tọa độ (khi người dùng chọn điểm trên bản đồ)."""
    cache_key = f"reverse:{lat:.6f}:{lon:.6f}"
    cached = _cache_get(cache_key)
    if cached is not None and cached:
        return cached[0]

    try:
        response = httpx.get(
            f"{NOMINATIM_BASE_URL}/reverse",
            params={"lat": str(lat), "lon": str(lon), "format": "jsonv2"},
            headers=_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except httpx.ConnectError as exc:
        logger.info(
            "Nominatim unavailable; using Photon fallback (%s)",
            type(exc).__name__,
        )
        result = _reverse_geocode_photon(lat, lon)
        _cache_put(cache_key, [result])
        return result
    except httpx.HTTPError as exc:
        _raise_upstream_error(exc)

    payload = response.json()
    if not isinstance(payload, dict) or "error" in payload:
        raise NotFoundException(
            message="Không tìm thấy địa điểm nào tại tọa độ này!",
            error_code="GEOCODE_NOT_FOUND",
        )

    try:
        result = GeocodeResult.model_validate(payload)
    except Exception as exc:
        raise NotFoundException(
            message="Không tìm thấy địa điểm nào tại tọa độ này!",
            error_code="GEOCODE_NOT_FOUND",
        ) from exc

    _cache_put(cache_key, [result])
    return result
