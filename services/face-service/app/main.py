"""Face-service entrypoint: keeps one worker running per enabled camera."""

from __future__ import annotations

import logging
import signal
import sys
import threading
import time
from dataclasses import asdict

from .api_client import ApiClient
from .cameras.registry import build_camera
from .config import settings
from .embed_api import build_embed_app
from .face_engine import FaceEngine
from .worker import CameraWorker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("face-service")


class Supervisor:
    def __init__(self) -> None:
        self.api = ApiClient()
        self.engine = FaceEngine()
        self.workers: dict[str, CameraWorker] = {}
        self.sigs: dict[str, tuple] = {}
        self.running = True

    def _run_embed_api(self) -> None:
        import uvicorn

        uvicorn.run(
            build_embed_app(self.engine),
            host=settings.embed_api_host,
            port=settings.embed_api_port,
            log_level="warning",
        )

    def sync(self) -> None:
        """Start workers for new cameras, stop them for removed/disabled ones."""
        try:
            cameras = self.api.fetch_cameras()
        except Exception:
            log.warning("Could not fetch camera list; keeping current workers", exc_info=True)
            return

        wanted = {config.id: config for config in cameras}
        wanted_sigs = {
            config.id: tuple(sorted(asdict(config).items()))
            for config in cameras
        }

        for camera_id in list(self.workers):
            if (
                camera_id not in wanted
                or not self.workers[camera_id].is_alive()
                or self.sigs.get(camera_id) != wanted_sigs.get(camera_id)
            ):
                log.info("Restarting worker %s (config changed)", camera_id)
                self.sigs.pop(camera_id, None)
                self.workers.pop(camera_id).stop()

        for camera_id, config in wanted.items():
            if camera_id in self.workers:
                continue
            worker = CameraWorker(build_camera(config), self.engine, self.api)
            worker.start()
            self.workers[camera_id] = worker
            self.sigs[camera_id] = wanted_sigs[camera_id]
            log.info("Started worker for %s (%s)", config.name, config.brand)

    def shutdown(self, *_args) -> None:
        log.info("Shutting down")
        self.running = False
        for worker in self.workers.values():
            worker.stop()

    def serve_forever(self) -> None:
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

        while self.running:
            self.sync()
            time.sleep(settings.camera_refresh_seconds)


def main() -> int:
    supervisor = Supervisor()

    embed_thread = threading.Thread(
        target=supervisor._run_embed_api,
        name="embed-api",
        daemon=True,
    )
    embed_thread.start()

    supervisor.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
