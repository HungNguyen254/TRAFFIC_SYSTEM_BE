from app.core.config import settings


def test_settings_has_jwt_and_gemini_config():
    assert hasattr(settings, "JWT_SECRET_KEY")
    assert hasattr(settings, "JWT_ALGORITHM")
    assert hasattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES")
    assert hasattr(settings, "GEMINI_API_KEY")
    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0
