"""Axis adapter — RTSP plus the VAPIX metadata event stream.

Axis devices do not push events over a plain HTTP multipart stream the way
Hikvision and Dahua do. Instead the analytics application (AXIS Object
Analytics, AXIS Face Detector, …) publishes ONVIF topics, and those are read
either through an ONVIF PullPoint subscription or from the RTSP metadata
track. PullPoint is used here: it needs no video decoding and reconnects
cleanly, and the JPEG for each event comes from the snapshot CGI.

Where onvif-zeep is unavailable the adapter reports that it has no event
source, which drops the camera onto the ordinary server-side RTSP path — the
same behaviour as any other camera without an edge engine.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

from .base import BaseCamera, DeviceEvent

log = logging.getLogger(__name__)

# ONVIF topics an Axis analytics app raises when a person is seen or a line is
# crossed. Matched case-insensitively as substrings of the full topic path.
INTERESTING_TOPICS = (
    "RuleEngine/ObjectDetect",
    "VideoAnalytics/ObjectAnalytics",
    "RuleEngine/FaceDetect",
    "RuleEngine/LineDetector",
    "RuleEngine/CrossLineDetector",
    "RuleEngine/MotionRegionDetector",
)

# How long each PullMessages call may block before we loop again — long enough
# to be a real long-poll, short enough to notice a stop request.
PULL_TIMEOUT = "PT30S"
PULL_LIMIT = 20


class AxisCamera(BaseCamera):
    brand = "axis"

    def rtsp_url(self) -> str:
        if self.config.rtsp_url:
            return self.config.rtsp_url
        # media.amp is the VAPIX main stream; the query keeps H.264 rather than
        # letting the device negotiate MJPEG on older firmware.
        return (
            f"rtsp://{self.credentials}{self.config.host}:554"
            "/axis-media/media.amp?videocodec=h264"
        )

    def supports_device_events(self) -> bool:
        return self.config.use_device_face_engine and _onvif_available()

    def snapshot(self) -> bytes | None:
        """Grab a still from the VAPIX image CGI."""
        try:
            response = self.http_get("/axis-cgi/jpg/image.cgi")
            response.raise_for_status()
            body = response.content or b""
            return body if body.startswith(b"\xff\xd8") else None
        except Exception:
            log.warning("Snapshot failed for %s", self.config.name, exc_info=True)
            return None

    def device_events(self) -> Iterator[DeviceEvent]:
        """Long-poll the device's ONVIF PullPoint for analytics events."""
        from onvif import ONVIFCamera

        device = ONVIFCamera(
            self.config.host,
            self.config.port,
            self.config.username or "",
            self.config.password or "",
        )
        events = device.create_events_service()
        pullpoint = device.create_pullpoint_service()
        # Keeping a handle on the events service stops zeep from garbage
        # collecting the subscription mid-stream.
        del events

        while True:
            request = pullpoint.create_type("PullMessages")
            request.Timeout = PULL_TIMEOUT
            request.MessageLimit = PULL_LIMIT
            response = pullpoint.PullMessages(request)

            for message in getattr(response, "NotificationMessage", []) or []:
                event = self._parse_message(message)
                if event is not None:
                    yield event

    def _parse_message(self, message) -> DeviceEvent | None:
        topic = str(getattr(getattr(message, "Topic", None), "_value_1", "") or "")
        if not any(known.lower() in topic.lower() for known in INTERESTING_TOPICS):
            return None

        data = self._data_items(message)
        # Axis reports the end of an event with the same topic and state false;
        # only the rising edge is a crossing.
        state = data.get("active") or data.get("state") or data.get("Active")
        if state is not None and str(state).lower() in {"0", "false"}:
            return None

        direction = self.direction_for_purpose() or _direction_from_data(data)
        return DeviceEvent(
            camera_id=self.config.id,
            direction=direction,
            image=self.snapshot(),
        )

    @staticmethod
    def _data_items(message) -> dict[str, str]:
        """Flatten the SimpleItem name/value pairs carried by a notification."""
        items: dict[str, str] = {}
        data = getattr(getattr(message, "Message", None), "_value_1", None)
        if data is None:
            return items

        for group in ("Source", "Key", "Data"):
            section = getattr(data, group, None)
            for item in getattr(section, "SimpleItem", None) or []:
                name = getattr(item, "Name", None)
                if name is not None:
                    items[str(name)] = str(getattr(item, "Value", ""))
        return items


def _direction_from_data(data: dict[str, str]) -> str | None:
    """Read a crossing direction out of the event's SimpleItems."""
    for key in ("direction", "Direction", "crossingDirection"):
        value = data.get(key)
        if not value:
            continue
        lowered = value.lower()
        if lowered in {"in", "enter", "entering", "lefttoright", "left-right"}:
            return "in"
        if lowered in {"out", "exit", "exiting", "righttoleft", "right-left"}:
            return "out"
    return None


def _onvif_available() -> bool:
    try:
        import onvif  # noqa: F401
    except ImportError:
        log.warning("onvif-zeep is not installed; Axis events fall back to RTSP capture")
        return False
    return True
