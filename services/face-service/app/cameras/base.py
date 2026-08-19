"""Camera abstraction layer.

Every brand adapter exposes the same two things: an RTSP URL to pull frames
from, and an optional stream of face/crossing events produced by the camera's
own engine. Adding a new brand means adding one subclass — nothing in the
pipeline changes.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import requests
from requests.auth import HTTPDigestAuth

log = logging.getLogger(__name__)


@dataclass(slots=True)
class CameraConfig:
    id: str
    name: str
    brand: str
    purpose: str  # entry | exit | bidirectional | monitor
    host: str
    port: int = 80
    username: str | None = None
    password: str | None = None
    rtsp_url: str | None = None
    use_device_face_engine: bool = False
    location: str | None = None
    analytics: list[str] = field(default_factory=list)
    analytics_config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> CameraConfig:
        return cls(
            id=data["id"],
            name=data["name"],
            brand=data.get("brand", "onvif"),
            purpose=data.get("purpose", "bidirectional"),
            host=data["host"],
            port=data.get("port", 80),
            username=data.get("username"),
            password=data.get("password"),
            rtsp_url=data.get("rtsp_url"),
            use_device_face_engine=data.get("use_device_face_engine", False),
            location=data.get("location"),
            analytics=data.get("analytics") or [],
            analytics_config=data.get("analytics_config") or {},
        )


@dataclass(slots=True)
class DeviceEvent:
    """A face/crossing event emitted by the camera itself."""

    camera_id: str
    direction: str | None  # 'in' | 'out' | None
    image: bytes | None
    confidence: float | None = None


class BaseCamera(ABC):
    """Common contract for every supported camera brand."""

    #: value stored in the `cameras.brand` column
    brand: str = "generic"

    def __init__(self, config: CameraConfig) -> None:
        self.config = config

    @property
    def credentials(self) -> str:
        if not self.config.username:
            return ""
        return f"{self.config.username}:{self.config.password or ''}@"

    @abstractmethod
    def rtsp_url(self) -> str:
        """Full RTSP URL of the main stream, credentials included."""

    def supports_device_events(self) -> bool:
        return False

    def device_events(self) -> Iterator[DeviceEvent]:
        """Yield events from the camera's built-in engine.

        The default implementation yields nothing, which makes server-side
        recognition the fallback for every camera that lacks an engine.
        """
        return iter(())

    def direction_for_purpose(self) -> str | None:
        if self.config.purpose == "entry":
            return "in"
        if self.config.purpose == "exit":
            return "out"
        return None

    # ------------------------------------------------------------- HTTP glue
    def http_get(self, path: str, *, stream: bool = False, timeout: tuple[float, float | None] | None = None):
        """Authenticated HTTP GET against the camera's HTTP API.

        Both vendors require Digest auth on their event/snapshot endpoints.
        """
        timeout = timeout or (10.0, 30.0)
        url = f"http://{self.config.host}:{self.config.port}{path}"
        auth = HTTPDigestAuth(self.config.username or "", self.config.password or "")
        return requests.get(url, auth=auth, stream=stream, timeout=timeout)

    def fetch_remote_image(self, url: str) -> bytes | None:
        """Download a snapshot the device referenced inside an event."""
        try:
            response = self.http_get(url)
            response.raise_for_status()
            return response.content or None
        except requests.RequestException:
            log.warning("Could not fetch event image for %s", self.config.name, exc_info=True)
            return None

    @staticmethod
    def extract_jpeg(raw: bytes) -> bytes | None:
        """Pull the first JPEG segment out of a multipart/XML event body."""
        start = raw.find(b"\xff\xd8\xff")
        if start == -1:
            return None
        end = raw.rfind(b"\xff\xd9")
        if end <= start:
            return None
        return raw[start : end + 2]

    @staticmethod
    def read_boundary(content_type: str) -> str | None:
        """Parse the boundary token from a multipart Content-Type header."""
        match = re.search(r"boundary=([A-Za-z0-9'()+_,.\-/:=? \x20]*)", content_type, re.I)
        return match.group(1).strip().strip('"') if match else None
