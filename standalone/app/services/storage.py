"""Face-crop storage with a retention policy."""

import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from ..config import settings

log = logging.getLogger(__name__)


def media_root() -> Path:
    root = Path(settings.media_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_face_image(data: bytes, at: datetime) -> str:
    """Store a JPEG face crop under faces/YYYY/MM/DD/ and return its relative path."""
    folder = Path("faces") / f"{at:%Y}" / f"{at:%m}" / f"{at:%d}"
    (media_root() / folder).mkdir(parents=True, exist_ok=True)

    relative = folder / f"{uuid.uuid4().hex}.jpg"
    (media_root() / relative).write_bytes(data)
    return relative.as_posix()


def purge_expired_images() -> int:
    """Delete face crops older than the retention window.

    Statistical records (events, stays, night counts) survive; only the raw
    biometric imagery is removed, which is what the privacy policy requires.
    """
    if settings.face_image_retention_days <= 0:
        return 0

    cutoff = datetime.now() - timedelta(days=settings.face_image_retention_days)
    removed = 0

    faces_dir = media_root() / "faces"
    if not faces_dir.exists():
        return 0

    for path in faces_dir.rglob("*.jpg"):
        try:
            if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            log.warning("Could not purge %s", path)

    return removed
