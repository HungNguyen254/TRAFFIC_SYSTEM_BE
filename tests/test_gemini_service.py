import pytest
import httpx
from fastapi import HTTPException
from app.services.gemini_service import GeminiService
from app.core.config import settings

@pytest.mark.asyncio
async def test_gemini_service_generate_response_success(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-api-key")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")

    mock_response_data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "Xin chào! Tôi có thể giúp gì cho bạn?"}
                    ],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ]
    }

    async def mock_post(*args, **kwargs):
        return httpx.Response(200, json=mock_response_data, request=httpx.Request("POST", "http://test"))

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    service = GeminiService()
    contents = [
        {"role": "user", "parts": [{"text": "Chào bạn"}]}
    ]
    response = await service.generate_response(contents=contents)
    assert response == "Xin chào! Tôi có thể giúp gì cho bạn?"

@pytest.mark.asyncio
async def test_gemini_service_missing_api_key(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    service = GeminiService()
    with pytest.raises(HTTPException) as exc_info:
        await service.generate_response([{"role": "user", "parts": [{"text": "Hello"}]}])
    assert exc_info.value.status_code == 503
    assert "GEMINI_API_KEY chưa được cấu hình" in exc_info.value.detail

@pytest.mark.asyncio
async def test_gemini_service_handles_quota_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-api-key")

    async def mock_post_429(*args, **kwargs):
        return httpx.Response(429, json={"error": {"message": "Resource exhausted"}}, request=httpx.Request("POST", "http://test"))

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_429)

    service = GeminiService()
    with pytest.raises(HTTPException) as exc_info:
        await service.generate_response([{"role": "user", "parts": [{"text": "Hello"}]}])
    assert exc_info.value.status_code == 429

@pytest.mark.asyncio
async def test_gemini_service_handles_upstream_error(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-api-key")

    async def mock_post_500(*args, **kwargs):
        return httpx.Response(500, text="Internal Error", request=httpx.Request("POST", "http://test"))

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_500)

    service = GeminiService()
    with pytest.raises(HTTPException) as exc_info:
        await service.generate_response([{"role": "user", "parts": [{"text": "Hello"}]}])
    assert exc_info.value.status_code == 502
