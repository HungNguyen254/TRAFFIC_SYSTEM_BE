from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str
    ENVIRONMENT: str
    DEBUG: bool
    HOST: str
    PORT: int

    ALLOWED_ORIGINS: list[str]

    DATABASE_URL: str
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
