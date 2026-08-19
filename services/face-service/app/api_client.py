"""Thin HTTP client for the backend API."""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone

import requests

from .cameras.base import CameraConfig
from .config import settings

log = logging.getLogger(__name__)


class ApiClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers["X-Service-Key"] = settings.service_api_key
        self.base = settings.api_base_url.rstrip("/")

    def fetch_cameras(self) -> list[CameraConfig]:
        response = self.session.get(f"{self.base}/api/cameras/stream-config", timeout=15)
        response.raise_for_status()
        return [CameraConfig.from_api(item) for item in response.json()]

    def submit_detection(
        self,
        camera_id: str,
        embedding: list[float],
        image: bytes | None,
        confidence: float | None,
        quality: float | None,
        direction_hint: str | None,
        detected_at: datetime | None = None,
        gender: str | None = None,
        age: int | None = None,
    ) -> dict | None:
        payload = {
            "camera_id": camera_id,
            "embedding": embedding,
            "confidence": confidence,
            "quality": quality,
            "direction_hint": direction_hint,
            "gender": gender,
            "age": age,
            "detected_at": (detected_at or datetime.now(timezone.utc)).isoformat(),
        }
        if image:
            payload["image_base64"] = base64.b64encode(image).decode()

        try:
            response = self.session.post(f"{self.base}/api/recognize", json=payload, timeout=20)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            log.warning("Failed to submit detection for camera %s", camera_id, exc_info=True)
            return None

    def submit_alert(
        self,
        camera_id: str,
        module: str,
        title: str,
        severity: str,
        detail: dict | None = None,
        image: bytes | None = None,
    ) -> None:
        payload = {
            "camera_id": camera_id,
            "module": module,
            "title": title,
            "severity": severity,
            "detail": detail or {},
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        if image:
            payload["image_base64"] = base64.b64encode(image).decode()

        try:
            response = self.session.post(f"{self.base}/api/alerts", json=payload, timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            log.warning("Failed to submit %s alert for camera %s", module, camera_id, exc_info=True)

    def heartbeat(self, camera_id: str, online: bool) -> None:
        try:
            self.session.post(
                f"{self.base}/api/cameras/{camera_id}/heartbeat",
                params={"online": online},
                timeout=10,
            )
        except requests.RequestException:
            log.debug("Heartbeat failed for camera %s", camera_id)
