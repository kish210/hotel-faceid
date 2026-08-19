"""Foscam adapter — RTSP plus the CGIProxy polling API.

Foscam devices expose one CGI entry point, ``/cgi-bin/CGIProxy.fcgi``, where
the command and the credentials all travel as query parameters and the answer
is a small XML document. There is no push stream to attach to, so the alarm
state is polled: ``getDevState`` reports ``motionDetectAlarm`` (0 disabled,
1 quiet, 2 firing), and a transition into 2 is the event.

Foscam has no on-board face engine, so "use the camera's own engine" means the
camera's motion alarm decides *when* to grab a frame — our own recogniser still
does the identifying.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterator
from urllib.parse import quote

import requests

from .base import BaseCamera, DeviceEvent

log = logging.getLogger(__name__)

# Foscam firmware answers slowly under load; polling faster buys nothing.
POLL_SECONDS = 2.0
ALARM_FIRING = "2"


class FoscamCamera(BaseCamera):
    brand = "foscam"

    def rtsp_url(self) -> str:
        if self.config.rtsp_url:
            return self.config.rtsp_url
        # videoMain is the H.264 main stream on every current Foscam model;
        # the RTSP port is 88 on the HD range and 554 on the older ones.
        port = 88 if self.config.port == 88 else 554
        return f"rtsp://{self.credentials}{self.config.host}:{port}/videoMain"

    def supports_device_events(self) -> bool:
        return self.config.use_device_face_engine

    # ------------------------------------------------------------- CGI glue
    def _cgi(self, command: str) -> str:
        """Build a CGIProxy URL. Credentials are query parameters here, not
        digest auth, so they must be percent-encoded."""
        user = quote(self.config.username or "", safe="")
        password = quote(self.config.password or "", safe="")
        return (
            f"http://{self.config.host}:{self.config.port}/cgi-bin/CGIProxy.fcgi"
            f"?cmd={command}&usr={user}&pwd={password}"
        )

    def _get(self, command: str, *, timeout: float = 10.0) -> requests.Response:
        return requests.get(self._cgi(command), timeout=(5.0, timeout))

    def snapshot(self) -> bytes | None:
        try:
            response = self._get("snapPicture2", timeout=15.0)
            response.raise_for_status()
            body = response.content or b""
            return body if body.startswith(b"\xff\xd8") else None
        except Exception:
            log.warning("Snapshot failed for %s", self.config.name, exc_info=True)
            return None

    def device_events(self) -> Iterator[DeviceEvent]:
        """Poll the device alarm state and yield on each rising edge."""
        previously_firing = False

        while True:
            try:
                response = self._get("getDevState")
                response.raise_for_status()
                firing = _field(response.text, "motionDetectAlarm") == ALARM_FIRING
            except requests.RequestException:
                log.warning("Foscam state poll failed for %s", self.config.name, exc_info=True)
                # Let the worker reconnect rather than spinning on a dead device.
                return

            if firing and not previously_firing:
                image = self.snapshot()
                if image is not None:
                    yield DeviceEvent(
                        camera_id=self.config.id,
                        direction=self.direction_for_purpose(),
                        image=image,
                    )

            previously_firing = firing
            time.sleep(POLL_SECONDS)


def _field(text: str, name: str) -> str | None:
    match = re.search(rf"<{name}>([^<]*)</{name}>", text, re.I)
    return match.group(1).strip() if match else None
