import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE_SEARCH = [
    {
        "place_id": 1,
        "display_name": "Bến Thành, Quận 1, TP.HCM",
        "lat": "10.7724",
        "lon": "106.6980",
        "type": "marketplace",
        "category": "shop",
        "importance": 0.8,
    }
]

SAMPLE_REVERSE = {
    "place_id": 2,
    "display_name": "Phố Nagarakretagama, Jakarta",
    "lat": "-6.2",
    "lon": "106.8",
    "type": "residential",
    "category": "boundary",
}

SAMPLE_PHOTON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "osm_type": "R",
                "osm_id": 198437,
                "osm_key": "water",
                "osm_value": "lake",
                "name": "Hồ Hoàn Kiếm",
                "district": "Hoàn Kiếm",
                "city": "Hà Nội",
                "country": "Việt Nam",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [105.8525357, 21.0288313],
            },
        }
    ],
}


@pytest.fixture(autouse=True)
def clear_cache():
    from app.services import geocoding_service

    geocoding_service._cache.clear()
    yield
    geocoding_service._cache.clear()


def test_search_requires_min_3_chars():
    response = client.get("/api/v1/geocode/search", params={"q": "ha"})
    assert response.status_code == 422


def test_search_validates_lat_lon_bounds():
    response = client.get("/api/v1/geocode/search", params={"q": "hanoi", "limit": 0})
    assert response.status_code == 422
    response = client.get("/api/v1/geocode/search", params={"q": "hanoi", "limit": 99})
    assert response.status_code == 422


def test_search_success(monkeypatch):
    def fake_get(url, **kwargs):
        return httpx.Response(200, json=SAMPLE_SEARCH, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    response = client.get("/api/v1/geocode/search", params={"q": "ben thanh"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data[0]["lat"] == pytest.approx(10.7724)
    assert data[0]["lon"] == pytest.approx(106.6980)


def test_search_accepts_four_coordinate_viewbox(monkeypatch):
    def fake_get(url, **kwargs):
        assert kwargs["params"]["viewbox"] == "105.3,21.5,106.1,20.5"
        return httpx.Response(200, json=SAMPLE_SEARCH, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    response = client.get(
        "/api/v1/geocode/search",
        params={"q": "hanoi", "viewbox": "105.3,21.5,106.1,20.5"},
    )
    assert response.status_code == 200


def test_search_uses_photon_when_nominatim_connection_fails(monkeypatch):
    def fake_get(url, **kwargs):
        if "nominatim.openstreetmap.org" in url:
            raise httpx.ConnectError(
                "connection reset",
                request=httpx.Request("GET", url),
            )
        assert url == "https://photon.komoot.io/api/"
        assert kwargs["params"]["bbox"] == "105.3,20.5,106.1,21.5"
        assert "User-Agent" in kwargs["headers"]
        return httpx.Response(
            200,
            json=SAMPLE_PHOTON,
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    response = client.get(
        "/api/v1/geocode/search",
        params={"q": "Hoan Kiem", "viewbox": "105.3,21.5,106.1,20.5"},
    )
    assert response.status_code == 200
    result = response.json()["data"][0]
    assert result["display_name"] == "Hồ Hoàn Kiếm, Hoàn Kiếm, Hà Nội, Việt Nam"
    assert result["lat"] == pytest.approx(21.0288313)
    assert result["lon"] == pytest.approx(105.8525357)


def test_reverse_rejects_out_of_range_coords():
    response = client.get("/api/v1/geocode/reverse", params={"lat": 95, "lon": 0})
    assert response.status_code == 422
    response = client.get("/api/v1/geocode/reverse", params={"lat": 0, "lon": -200})
    assert response.status_code == 422


def test_reverse_success(monkeypatch):
    def fake_get(url, **kwargs):
        return httpx.Response(200, json=SAMPLE_REVERSE, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    response = client.get("/api/v1/geocode/reverse", params={"lat": -6.2, "lon": 106.8})
    assert response.status_code == 200
    assert response.json()["data"]["display_name"] == SAMPLE_REVERSE["display_name"]


def test_reverse_reports_error_when_both_geocoders_are_unavailable(monkeypatch):
    def fake_get(url, **kwargs):
        raise httpx.ConnectError(
            "connection reset",
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    response = client.get(
        "/api/v1/geocode/reverse",
        params={"lat": 21.0285, "lon": 105.8542},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "GEOCODE_FALLBACK_ERROR"
    assert "Photon cũng không khả dụng" in response.json()["message"]


def test_reverse_uses_photon_when_nominatim_connection_fails(monkeypatch):
    def fake_get(url, **kwargs):
        if "nominatim.openstreetmap.org" in url:
            raise httpx.ConnectError(
                "connection reset",
                request=httpx.Request("GET", url),
            )
        assert url == "https://photon.komoot.io/reverse"
        assert "User-Agent" in kwargs["headers"]
        return httpx.Response(
            200,
            json=SAMPLE_PHOTON,
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    response = client.get(
        "/api/v1/geocode/reverse",
        params={"lat": 21.029, "lon": 105.854},
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["display_name"] == "Hồ Hoàn Kiếm, Hoàn Kiếm, Hà Nội, Việt Nam"
    assert result["lat"] == pytest.approx(21.029)
    assert result["lon"] == pytest.approx(105.854)


def test_reverse_not_found(monkeypatch):
    def fake_get(url, **kwargs):
        return httpx.Response(200, json={"error": "unable to geocode"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    response = client.get("/api/v1/geocode/reverse", params={"lat": 0, "lon": 0})
    assert response.status_code == 404
