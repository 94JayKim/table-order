"""환경 변수에서 설정을 읽는다."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./app.db"
    cors_origins: list[str] = ["http://localhost:8501", "http://localhost:8502"]
    admin_token: str = "change-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()
