"""Hikvision adapter — RTSP plus ISAPI event alert stream.

The camera exposes a persistent multipart stream on
``/ISAPI/Event/notification/alertStream``. Each event part is an XML
``EventNotificationAlert``; face grabs additionally carry a ``facePicURL``
element whose value we must download separately.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator

from .base import BaseCamera, DeviceEvent

log = logging.getLogger(__name__)

# ISAPI event names that mean "a person crossed the line / a face was captured"
FACE_EVENT_TYPES = {
    "faceCapture",
    "faceDetection",
    "facesnap",
    "FaceDetection",
    "linedetection",
    "fielddetection",
    "regionEntrance",
    "regionExiting",
}


class HikvisionCamera(BaseCamera):
    brand = "hikvision"

    def rtsp_url(self) -> str:
        if self.config.rtsp_url:
            return self.config.rtsp_url
        # channel 101 = camera 1, main stream
        return f"rtsp://{self.credentials}{self.config.host}:554/Streaming/Channels/101"

    def supports_device_events(self) -> bool:
        return self.config.use_device_face_engine

    def _isapi(self, path: str) -> str:
        return f"http://{self.config.host}:{self.config.port}{path}"

    def device_events(self) -> Iterator[DeviceEvent]:
        """Consume the ISAPI multipart alertStream.

        The camera holds the connection open and pushes one part per event,
        so this is a long-lived generator, not a poll.
        """
        url = self._isapi("/ISAPI/Event/notification/alertStream")

        with self.http_get(url, stream=True, timeout=(10.0, None)) as response:
            response.raise_for_status()
            buffer = b""
            boundary = self.read_boundary(response.headers.get("Content-Type", ""))

            # Without a boundary the camera streams each alert as plain XML
            # separated by a blank line; fall back to that delimiter.
            delimiter = f"--{boundary}".encode() if boundary else b"\n\n"

            for chunk in response.iter_content(chunk_size=4096):
                if not chunk:
                    continue
                buffer += chunk

                while delimiter in buffer:
                    part, buffer = buffer.split(delimiter, 1)
                    event = self._parse_part(part)
                    if event is not None:
                        yield event

    def _parse_part(self, part: bytes) -> DeviceEvent | None:
        text = part.decode("utf-8", errors="ignore")
        event_type = self._field(text, "eventType")
        if event_type is None or event_type.lower() not in {t.lower() for t in FACE_EVENT_TYPES}:
            return None

        # The snapshot may be embedded in the part, or referenced by a URL
        # that must be fetched (facePicURL / snapshotURL).
        image = self.extract_jpeg(part)
        if image is None:
            for element in ("facePicURL", "snapshotURL", "pictureURL"):
                url = self._field(text, element)
                if url:
                    image = self.fetch_remote_image(url)
                    if image:
                        break

        direction = self.direction_for_purpose()
        if direction is None:
            # Line-crossing tells us which way they went even on a shared door.
            if re.search(r"<detectionTarget>.*?left-right.*?</detectionTarget>", text, re.S):
                direction = "in"
            elif re.search(r"<detectionTarget>.*?right-left.*?</detectionTarget>", text, re.S):
                direction = "out"
            elif "regionEntrance" in event_type.lower() or (
                text and "<direction>Enter</direction>" in text
            ):
                direction = "in"
            elif "regionExiting" in event_type.lower() or (
                text and "<direction>Exit</direction>" in text
            ):
                direction = "out"

        # Face capture events embed an <appear>/<disappear> state signal.
        state = self._field(text, "eventState")
        if direction is None and state and "disappear" in state.lower():
            direction = "out" if self.config.purpose == "bidirectional" else None

        return DeviceEvent(camera_id=self.config.id, direction=direction, image=image)

    @staticmethod
    def _field(text: str, name: str) -> str | None:
        match = re.search(rf"<{name}[^>]*>([^<]+)</{name}>", text, re.I | re.S)
        return match.group(1).strip() if match else None


class HikvisionBidirectionalCamera(HikvisionCamera):
    """Same adapter; kept for configs that set a purpose on the device."""