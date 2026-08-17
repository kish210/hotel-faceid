from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_base_url: str = "http://localhost:8000"
    service_api_key: str = "change-me-service-key"

    # Detection / quality gates
    face_detect_threshold: float = 0.6
    min_face_size: int = 60
    frame_sample_rate: int = 5

    # InsightFace
    onnx_provider: str = "CPUExecutionProvider"
    model_pack: str = "buffalo_l"
    det_size: int = 640

    # Stream handling
    reconnect_delay_seconds: int = 5
    heartbeat_interval_seconds: int = 30
    camera_refresh_seconds: int = 60

    # HTTP embed API (used for photo-based guest search)
    embed_api_host: str = "0.0.0.0"
    embed_api_port: int = 8001


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
