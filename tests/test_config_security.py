import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_dev_environment_permits_default_secret():
    s = Settings(
        ENVIRONMENT="dev",
        JWT_SECRET_KEY="dev-secret-key-change-in-production-must-be-long-enough",
        _env_file=None,
    )
    assert s.JWT_SECRET_KEY == "dev-secret-key-change-in-production-must-be-long-enough"


def test_prod_environment_rejects_default_secret():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="prod",
            JWT_SECRET_KEY="dev-secret-key-change-in-production-must-be-long-enough",
            _env_file=None,
        )
    assert "JWT_SECRET_KEY must be changed" in str(exc_info.value)


def test_prod_environment_rejects_short_secret():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="prod",
            JWT_SECRET_KEY="too-short",
            _env_file=None,
        )
    assert "JWT_SECRET_KEY must be changed" in str(exc_info.value)


def test_prod_environment_accepts_custom_secure_secret():
    custom_secret = "a-very-long-and-secure-random-secret-key-for-production-32bytes"
    s = Settings(ENVIRONMENT="prod", JWT_SECRET_KEY=custom_secret, _env_file=None)
    assert s.JWT_SECRET_KEY == custom_secret
