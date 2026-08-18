from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Portable default: a local SQLite file works without Postgres/pgvector.
    database_url: str = "sqlite:///./data/hotel_faceid.db"

    jwt_secret: str = "dev-secret-do-not-use-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    secret_encryption_key: str = ""
    service_api_key: str = "change-me-service-key"

    media_root: str = "./data/media"
    face_image_retention_days: int = 30

    face_match_threshold: float = 0.42
    event_debounce_seconds: int = 60

    stay_timeout_hours: int = 12
    hotel_timezone: str = "Asia/Tehran"

    # Photo-based guest search — where the face-service embed API lives.
    face_service_url: str = "http://127.0.0.1:8001"

    # Periodic email report.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    report_email_to: str = ""
    email_report_enabled: bool = False
    email_report_hour: int = 8

    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
