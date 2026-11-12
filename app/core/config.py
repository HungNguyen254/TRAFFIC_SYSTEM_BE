from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Traffic System BE"
    ENVIRONMENT: str = "dev"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    ALLOWED_ORIGINS: list[str] = ["http://127.0.0.1:5173"]

    DATABASE_URL: str = "sqlite:///./traffic.db"
    DIRECT_URL: str | None = None

    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production-must-be-long-enough"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE: int = 1440  # 24 hours

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "60/minute"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
