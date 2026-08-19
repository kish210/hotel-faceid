"""Per-camera capture worker.

One thread per camera. Cameras with their own face engine consume the vendor
event stream; the rest are processed frame-by-frame on this server.
"""

from __future__ import annotations

import logging
import threading
import time

import cv2
import numpy as np

from .analytics import FrameContext, build_pipeline
from .api_client import ApiClient
from .cameras.base import BaseCamera
from .config import settings
from .face_engine import FaceEngine, encode_jpeg

log = logging.getLogger(__name__)


class CameraWorker(threading.Thread):
    def __init__(self, camera: BaseCamera, engine: FaceEngine, api: ApiClient) -> None:
        super().__init__(name=f"cam-{camera.config.name}", daemon=True)
        self.camera = camera
        self.engine = engine
        self.api = api
        self._stop = threading.Event()
        self._last_heartbeat = 0.0

        self.analytics = (
            build_pipeline(
                camera.config.name,
                camera.config.analytics,
                camera.config.analytics_config,
            )
            if settings.analytics_enabled
            else []
        )
        if self.analytics:
            log.info(
                "Analytics on %s: %s",
                camera.config.name,
                ", ".join(module.id for module in self.analytics),
            )
        self._analytics_tick = 0

    def stop(self) -> None:
        self._stop.set()

    # ------------------------------------------------------------- lifecycle
    def run(self) -> None:
        while not self._stop.is_set():
            try:
                if self.camera.supports_device_events():
                    self._run_device_events()
                else:
                    self._run_rtsp()
            except Exception:
                log.exception("Worker for %s crashed; reconnecting", self.camera.config.name)

            self.api.heartbeat(self.camera.config.id, online=False)
            self._stop.wait(settings.reconnect_delay_seconds)

    # ------------------------------------------------------ server-side path
    def _run_rtsp(self) -> None:
        url = self.camera.rtsp_url()
        log.info("Opening RTSP stream for %s", self.camera.config.name)

        capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        # Keep the buffer tiny so we always analyse the freshest frame.
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not capture.isOpened():
            log.warning("Could not open stream for %s", self.camera.config.name)
            return

        frame_index = 0
        try:
            while not self._stop.is_set():
                ok, frame = capture.read()
                if not ok:
                    log.warning("Stream ended for %s", self.camera.config.name)
                    return

                self._beat()
                frame_index += 1
                if frame_index % settings.frame_sample_rate:
                    continue  # skip frames — full frame-rate inference is wasteful

                self._process_frame(frame)
        finally:
            capture.release()

    def _process_frame(self, frame: np.ndarray) -> None:
        faces = self.engine.detect(frame)
        self._run_analytics(frame, faces)

        for face in faces:
            self.api.submit_detection(
                camera_id=self.camera.config.id,
                embedding=face.embedding,
                image=encode_jpeg(face.crop),
                confidence=face.det_score,
                quality=face.quality,
                direction_hint=self.camera.direction_for_purpose(),
                gender=face.gender,
                age=face.age,
            )

    # ---------------------------------------------------------- analytics
    def _run_analytics(self, frame: np.ndarray, faces: list) -> None:
        """Feed the frame to this camera's modules.

        Analytics runs on a fraction of the frames recognition sees: a fight
        or an abandoned bag lasts seconds, so a lower rate loses nothing, and
        it keeps identification — the primary job — from being starved.
        """
        if not self.analytics:
            return

        self._analytics_tick += 1
        if self._analytics_tick % max(settings.analytics_frame_divisor, 1):
            return

        context = FrameContext(frame=frame, faces=[face.bbox for face in faces])

        for module in self.analytics:
            try:
                alert = module.process(context)
            except Exception:
                log.exception(
                    "Analytics module %s failed on %s", module.id, self.camera.config.name
                )
                continue

            if alert is not None:
                self.api.submit_alert(
                    camera_id=self.camera.config.id,
                    module=alert.module,
                    title=alert.title,
                    severity=alert.severity,
                    detail=alert.detail,
                    image=encode_jpeg(alert.frame) if alert.frame is not None else None,
                )

    # -------------------------------------------------------- edge-event path
    def _run_device_events(self) -> None:
        log.info("Subscribing to device events for %s", self.camera.config.name)

        for event in self.camera.device_events():
            if self._stop.is_set():
                return
            self._beat()

            if not event.image:
                continue

            frame = cv2.imdecode(np.frombuffer(event.image, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue

            # The camera found a face; we still need our own embedding so that
            # identities stay comparable across brands.
            for face in self.engine.detect(frame):
                self.api.submit_detection(
                    camera_id=self.camera.config.id,
                    embedding=face.embedding,
                    image=encode_jpeg(face.crop),
                    confidence=event.confidence or face.det_score,
                    quality=face.quality,
                    direction_hint=event.direction or self.camera.direction_for_purpose(),
                    gender=face.gender,
                    age=face.age,
                )

    # ------------------------------------------------------------- internals
    def _beat(self) -> None:
        now = time.monotonic()
        if now - self._last_heartbeat >= settings.heartbeat_interval_seconds:
            self.api.heartbeat(self.camera.config.id, online=True)
            self._last_heartbeat = now
