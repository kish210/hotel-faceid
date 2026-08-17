"""Brand-neutral ONVIF adapter — the portable default.

Used when a camera's brand is unknown, or when its vendor SDK is unavailable.
Only requires ONVIF Profile S (media streaming), which every modern IP camera
from either vendor supports.
"""

from __future__ import annotations

import logging

from .base import BaseCamera

log = logging.getLogger(__name__)


class OnvifCamera(BaseCamera):
    brand = "onvif"

    def rtsp_url(self) -> str:
        if self.config.rtsp_url:
            return self.config.rtsp_url

        discovered = self._discover_stream_uri()
        if discovered:
            return discovered

        # Last resort: the most common default path.
        return f"rtsp://{self.credentials}{self.config.host}:554/Streaming/Channels/101"

    def _discover_stream_uri(self) -> str | None:
        """Ask the device for its own stream URI over ONVIF."""
        try:
            from onvif import ONVIFCamera as _ONVIF
        except ImportError:
            log.debug("onvif-zeep not installed; falling back to a default RTSP path")
            return None

        try:
            device = _ONVIF(
                self.config.host,
                self.config.port,
                self.config.username or "",
                self.config.password or "",
            )
            media = device.create_media_service()
            profile = media.GetProfiles()[0]

            request = media.create_type("GetStreamUri")
            request.ProfileToken = profile.token
            request.StreamSetup = {
                "Stream": "RTP-Unicast",
                "Transport": {"Protocol": "RTSP"},
            }
            uri = media.GetStreamUri(request).Uri
        except Exception:
            log.warning("ONVIF discovery failed for %s", self.config.host, exc_info=True)
            return None

        # The device returns a bare URI; inject credentials for ffmpeg/OpenCV.
        if self.credentials and "@" not in uri:
            uri = uri.replace("rtsp://", f"rtsp://{self.credentials}", 1)
        return uri


class GenericCamera(OnvifCamera):
    """Alias used when the brand column says 'generic'."""

    brand = "generic"
