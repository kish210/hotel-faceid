"""TOPSEE / Hisilicon OEM board adapter — the TH38J family and its cousins.

These are camera *modules* (TH38J3 and relatives) sold to integrators, who put
them in their own housings under their own names. That has one practical
consequence: there is no single RTSP path to rely on. The same board ships with
`/0`, `/11`, `/live/ch00_0` or `/onvif1` depending on whose firmware is on it,
and the label on the camera tells you nothing.

So this adapter finds the path instead of assuming it: ONVIF first, since most
of these boards answer it, then each known path in turn until one responds to
an RTSP DESCRIBE. The answer is remembered, so the search happens once.

Motion events come from polling the board's CGI, which is all these boards
offer — there is no push stream and no face engine on the device.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterator

import requests

from .base import BaseCamera, DeviceEvent, describe_rtsp
from .onvif_camera import OnvifCamera

log = logging.getLogger(__name__)

#: Paths these boards are shipped with, most common first.
CANDIDATE_PATHS = (
    "/0",
    "/1",
    "/11",
    "/12",
    "/live/ch00_0",
    "/live/ch0",
    "/onvif1",
    "/onvif2",
    "/media/video1",
    "/stream0",
    "/h264/ch1/main/av_stream",
    "/user=admin&password=&channel=1&stream=0.sdp",
)

POLL_SECONDS = 2.0


class TopseeCamera(OnvifCamera):
    """TOPSEE boards speak ONVIF, so the discovery there is worth trying first."""

    brand = "topsee"

    def __init__(self, config) -> None:
        super().__init__(config)
        self._resolved: str | None = None

    def rtsp_url(self) -> str:
        if self.config.rtsp_url:
            return self.config.rtsp_url
        if self._resolved:
            return self._resolved

        # ONVIF knows the real path when the board's firmware implements it.
        discovered = self._discover_stream_uri()
        if discovered:
            self._resolved = discovered
            log.info("%s: stream URI from ONVIF", self.config.name)
            return discovered

        found = self._probe_paths()
        if found:
            self._resolved = found
            log.info("%s: stream path found by probing (%s)", self.config.name, found.rsplit("@", 1)[-1])
            return found

        # Nothing answered; hand back the most common one so the worker's own
        # reconnect loop keeps trying rather than dying here.
        fallback = f"rtsp://{self.credentials}{self.config.host}:554{CANDIDATE_PATHS[0]}"
        log.warning("%s: no RTSP path answered, falling back to %s", self.config.name, CANDIDATE_PATHS[0])
        return fallback

    def _probe_paths(self) -> str | None:
        for path in CANDIDATE_PATHS:
            url = f"rtsp://{self.credentials}{self.config.host}:554{path}"
            if describe_rtsp(url):
                return url
        return None

    # ----------------------------------------------------------- CGI events
    def supports_device_events(self) -> bool:
        return self.config.use_device_face_engine

    def snapshot(self) -> bytes | None:
        """Hisilicon boards expose one of a couple of snapshot CGIs."""
        for path in ("/cgi-bin/snapshot.cgi", "/snapshot.cgi", "/tmpfs/auto.jpg", "/cgi-bin/hi3510/snap.cgi"):
            try:
                response = self.http_get(path)
                if response.status_code == 200 and response.content.startswith(b"\xff\xd8"):
                    return response.content
            except requests.RequestException:
                continue
        return None

    def device_events(self) -> Iterator[DeviceEvent]:
        """Poll the board's alarm state; yield on each rising edge."""
        previously_firing = False

        while True:
            try:
                response = self.http_get("/cgi-bin/hi3510/param.cgi?cmd=getmdalarm")
                firing = bool(re.search(r"md_switch\w*\s*=\s*[\"']?1", response.text, re.I))
            except requests.RequestException:
                log.warning("Alarm poll failed for %s", self.config.name, exc_info=True)
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
