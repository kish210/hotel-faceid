"""Dahua adapter — RTSP plus the CGI attach-to-event-manager stream.

Dahua pushes events as multipart text over ``/cgi-bin/eventManager.cgi``.
Every part looks like::

    Code=FaceDetection;action=Start;index=0;data={...json...}

Unlike Hikvision, the event body never embeds a JPEG — the frame must be
requested from ``snapshot.cgi`` ourselves.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from urllib.parse import quote

from .base import BaseCamera, DeviceEvent

log = logging.getLogger(__name__)

EVENT_CODES = "FaceDetection,FaceRecognition,CrossLineDetection,CrossRegionDetection"

# Codes we care about vs. motion/audio noise.
INTERESTING = {"FaceDetection", "FaceRecognition", "CrossLineDetection", "CrossRegionDetection"}


class DahuaCamera(BaseCamera):
    brand = "dahua"

    def rtsp_url(self) -> str:
        if self.config.rtsp_url:
            return self.config.rtsp_url
        return (
            f"rtsp://{self.credentials}{self.config.host}:554"
            "/cam/realmonitor?channel=1&subtype=0"
        )

    def supports_device_events(self) -> bool:
        return self.config.use_device_face_engine

    def device_events(self) -> Iterator[DeviceEvent]:
        """Attach to the Dahua event manager and yield face/crossing events."""
        url = (
            f"http://{self.config.host}:{self.config.port}"
            f"/cgi-bin/eventManager.cgi?action=attach&codes=[{quote(EVENT_CODES)}]"
        )

        with self.http_get(url, stream=True, timeout=(10.0, None)) as response:
            response.raise_for_status()
            buffer = b""
            boundary = self.read_boundary(response.headers.get("Content-Type", ""))

            # Dahua uses the literal "myboundary" marker, no matter what the
            # Content-Type header claims.
            marker = f"--{boundary}".encode() if boundary else b"--myboundary"

            for chunk in response.iter_content(chunk_size=4096):
                if not chunk:
                    continue
                buffer += chunk

                while marker in buffer:
                    part, buffer = buffer.split(marker, 1)
                    event = self._parse_event(part)
                    if event is not None:
                        yield event

    def _parse_event(self, raw: bytes) -> DeviceEvent | None:
        text = raw.decode("utf-8", errors="ignore")
        if "Code=" not in text:
            return None

        event = self._split_kv(text)
        code = event.get("Code", "")
        if code not in INTERESTING:
            return None
        # Only 'Start' actions are real crossings; 'Stop' closes the same event.
        if event.get("action", "").lower() == "stop":
            return None

        # Face detection enriches the payload with a JSON object describing
        # direction, bounding box etc.
        direction = self.direction_for_purpose()
        if direction is None:
            direction = self._direction_from_payload(code, event.get("data", ""))

        # No JPEG is ever embedded in Dahua event bodies — grab a live frame.
        image = self.extract_jpeg(raw) or self.snapshot()

        return DeviceEvent(camera_id=self.config.id, direction=direction, image=image)

    def snapshot(self) -> bytes | None:
        """Request a fresh JPEG from the camera's snapshot CGI."""
        try:
            response = self.http_get("/cgi-bin/snapshot.cgi?channel=1&noreq=0")
            response.raise_for_status()
            body = response.content or b""
            return body if body.startswith(b"\xff\xd8") else None
        except Exception:
            log.warning("Snapshot failed for %s", self.config.name, exc_info=True)
            return None

    @staticmethod
    def _split_kv(text: str) -> dict[str, str]:
        """Turn the ';'-separated header line (the one starting with Code=)
        into key/value pairs.

        Each multipart part still carries HTTP-ish headers (Content-Type,
        Content-Length) before the actual event line, so we skip down to the
        line that starts with ``Code=``.
        """
        out: dict[str, str] = {}
        for line in text.splitlines():
            if not line.startswith("Code="):
                continue
            for pair in line.split(";"):
                if "=" in pair:
                    key, _, value = pair.partition("=")
                    out[key.strip()] = value.strip()
            break
        return out

    @staticmethod
    def _direction_from_payload(code: str, data: str) -> str | None:
        payload: object = None
        if data:
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                payload = None
        if not isinstance(payload, dict):
            return None

        # Dahua JSON uses camelCase fields depending on firmware generation.
        for key in ("Direction", "RegionDirection", "CrossLineDirection"):
            value = payload.get(key)
            if isinstance(value, dict):
                value = value.get("Value")
            if not isinstance(value, str):
                continue
            lowered = value.lower()
            if lowered in {"enter", "lefttoright", "left-right"}:
                return "in"
            if lowered in {"exit", "righttoleft", "right-left"}:
                return "out"
        return None