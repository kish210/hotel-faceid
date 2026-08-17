"""Face detection and embedding.

RetinaFace (detection) + ArcFace (512-d embedding) via InsightFace's
`buffalo_l` pack — both models ship in one bundle and run under ONNXRuntime
on CPU or CUDA.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

from .config import settings

log = logging.getLogger(__name__)


@dataclass(slots=True)
class DetectedFace:
    bbox: tuple[int, int, int, int]
    embedding: list[float]
    det_score: float
    quality: float
    crop: np.ndarray


class FaceEngine:
    def __init__(self) -> None:
        from insightface.app import FaceAnalysis

        self.app = FaceAnalysis(
            name=settings.model_pack,
            root=settings.insightface_root,
            providers=[settings.onnx_provider],
            allowed_modules=["detection", "recognition"],
        )
        # ctx_id -1 selects CPU; any >= 0 selects that GPU device.
        ctx_id = 0 if "CUDA" in settings.onnx_provider else -1
        self.app.prepare(ctx_id=ctx_id, det_size=(settings.det_size, settings.det_size))
        log.info("Face engine ready (%s, %s)", settings.model_pack, settings.onnx_provider)

    def detect(self, frame: np.ndarray) -> list[DetectedFace]:
        results: list[DetectedFace] = []

        for face in self.app.get(frame):
            if face.det_score < settings.face_detect_threshold:
                continue

            x1, y1, x2, y2 = (int(v) for v in face.bbox)
            width, height = x2 - x1, y2 - y1
            if min(width, height) < settings.min_face_size:
                continue  # too small to identify reliably

            crop = _safe_crop(frame, x1, y1, x2, y2)
            if crop.size == 0:
                continue

            quality = _quality_score(crop, face.det_score)
            embedding = face.normed_embedding.astype(np.float32)

            results.append(
                DetectedFace(
                    bbox=(x1, y1, width, height),
                    embedding=embedding.tolist(),
                    det_score=float(face.det_score),
                    quality=quality,
                    crop=crop,
                )
            )

        return results


def _safe_crop(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int, margin: float = 0.2) -> np.ndarray:
    """Crop with margin, clamped to the frame — face boxes often touch the edge."""
    height, width = frame.shape[:2]
    pad_x = int((x2 - x1) * margin)
    pad_y = int((y2 - y1) * margin)

    return frame[
        max(y1 - pad_y, 0) : min(y2 + pad_y, height),
        max(x1 - pad_x, 0) : min(x2 + pad_x, width),
    ]


def _quality_score(crop: np.ndarray, det_score: float) -> float:
    """Combine sharpness and exposure into a 0..1 usability score.

    A blurry or badly exposed crop still yields an embedding, but a poor one —
    scoring it lets the API skip enrolling it as a reference vector.
    """
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    # Variance of Laplacian: low variance means out of focus.
    sharpness = min(cv2.Laplacian(gray, cv2.CV_64F).var() / 500.0, 1.0)
    # Penalise crops that are nearly black or blown out.
    brightness = float(gray.mean()) / 255.0
    exposure = 1.0 - abs(brightness - 0.5) * 2

    return round(float(0.5 * sharpness + 0.3 * exposure + 0.2 * det_score), 4)


def encode_jpeg(image: np.ndarray, quality: int = 85) -> bytes:
    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return buffer.tobytes() if ok else b""
