import httpx
from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse

from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response

router = APIRouter(prefix="/geocode", tags=["geocode"])

NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
# Nominatim yêu cầu một User-Agent định danh, request không có UA sẽ bị chặn (403)
REQUEST_HEADERS = {
    "User-Agent": "HanoiTrafficAI/1.0 (traffic forecasting student project)",
    "Accept": "application/json",
}


async def _proxy_nominatim(request: Request, path: str, params: dict) -> StandardResponse | JSONResponse:
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(
                f"{NOMINATIM_BASE_URL}/{path}", params=params, headers=REQUEST_HEADERS
            )
    except httpx.HTTPError:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "status_code": status.HTTP_502_BAD_GATEWAY,
                "message": "Không thể kết nối tới dịch vụ geocoding (Nominatim).",
                "error": None,
                "path": request.url.path,
            },
        )

    if response.status_code == status.HTTP_404_NOT_FOUND:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "status_code": status.HTTP_404_NOT_FOUND,
                "message": "Không tìm thấy địa điểm phù hợp.",
                "error": None,
                "path": request.url.path,
            },
        )
    if response.status_code != status.HTTP_200_OK:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "status_code": status.HTTP_502_BAD_GATEWAY,
                "message": f"Dịch vụ geocoding trả về mã lỗi {response.status_code}.",
                "error": None,
                "path": request.url.path,
            },
        )

    try:
        data = response.json()
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "status_code": status.HTTP_502_BAD_GATEWAY,
                "message": "Dịch vụ geocoding trả về dữ liệu không hợp lệ.",
                "error": None,
                "path": request.url.path,
            },
        )

    return success_response(request=request, message="Tra cứu địa điểm thành công", data=data)


@router.get(
    "/search",
    response_model=StandardResponse[list | dict],
    status_code=status.HTTP_200_OK,
    summary="Tìm địa điểm theo từ khóa (proxy Nominatim, giới hạn trong viewbox Hà Nội từ FE)",
)
@limiter.limit("30/minute")
async def search_places(
    request: Request,
    q: str = Query(min_length=3, max_length=200, description="Từ khóa tìm kiếm"),
    limit: int = Query(default=5, ge=1, le=10),
    viewbox: str | None = Query(default=None, description="west,north,east,south"),
):
    params = {
        "q": q,
        "limit": limit,
        "format": "jsonv2",
        "addressdetails": 1,
    }
    if viewbox:
        params["viewbox"] = viewbox
        params["bounded"] = 1
    return await _proxy_nominatim(request, "search", params)


@router.get(
    "/reverse",
    response_model=StandardResponse[list | dict],
    status_code=status.HTTP_200_OK,
    summary="Tra cứu tên địa điểm từ tọa độ (proxy Nominatim)",
)
@limiter.limit("30/minute")
async def reverse_geocode(
    request: Request,
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    zoom: int = Query(default=18, ge=0, le=18),
):
    params = {
        "lat": lat,
        "lon": lon,
        "zoom": zoom,
        "format": "jsonv2",
        "addressdetails": 1,
    }
    return await _proxy_nominatim(request, "reverse", params)
