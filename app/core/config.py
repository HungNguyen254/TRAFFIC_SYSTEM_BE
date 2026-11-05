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

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
