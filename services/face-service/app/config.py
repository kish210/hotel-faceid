from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Left empty, this follows API_PORT — the two settings drifting apart is
    # otherwise silent: the API moves to another port and the capture service
    # keeps calling the old one, so nothing is ever recognised. Set it
    # explicitly only when the API runs on a different machine.
    api_base_url: str = ""
    api_port: int = 8000
    service_api_key: str = "change-me-service-key"

    # Detection / quality gates
    face_detect_threshold: float = 0.6
    min_face_size: int = 60
    # Maximum head yaw/pitch in degrees before the quality score starts to
    # drop.  Faces beyond 2× this angle score near zero and are rarely enrolled
    # as reference vectors — they produce poor embeddings anyway.
    max_head_angle: float = 40.0
    frame_sample_rate: int = 5

    # Gender / age estimation (InsightFace genderage model)
    gender_detection: bool = True
    gender_min_quality: float = 0.35

    # InsightFace
    onnx_provider: str = "CPUExecutionProvider"
    model_pack: str = "buffalo_l"
    det_size: int = 640
    # Folder holding a `models/<pack>` directory. Empty means "look next to the
    # installation, then fall back to InsightFace's own ~/.insightface".
    model_root: str = ""

    # Analytics modules (fight, intrusion, plate reading…)
    analytics_enabled: bool = True
    # Analytics looks at one frame every N sampled frames. Face recognition
    # gets every sampled frame; analytics is the cheaper-but-second job.
    analytics_frame_divisor: int = 3
    # Where downloaded model packs live, matching the API's data/modules.
    module_root: str = "./data/modules"

    # Stream handling
    reconnect_delay_seconds: int = 5
    heartbeat_interval_seconds: int = 30
    camera_refresh_seconds: int = 60

    # HTTP embed API (used for photo-based guest search)
    embed_api_host: str = "0.0.0.0"
    embed_api_port: int = 8001


    @model_validator(mode="after")
    def _follow_api_port(self) -> "Settings":
        if not self.api_base_url:
            self.api_base_url = f"http://localhost:{self.api_port}"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
