"""Face detection and embedding.

RetinaFace (detection) + ArcFace (512-d embedding) via InsightFace's
`buffalo_l` pack — both models ship in one bundle and run under ONNXRuntime
on CPU or CUDA.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .config import settings

log = logging.getLogger(__name__)


def _model_root() -> Path | None:
    """Where InsightFace should look for `models/<pack>`.

    An explicit MODEL_ROOT wins. Otherwise the working directory is tried,
    which is where the packaged installation keeps its bundled models; None
    means "let InsightFace use its own default and download on demand".
    """
    if settings.model_root:
        return Path(settings.model_root)

    candidate = Path.cwd()
    return candidate if (candidate / "models" / settings.model_pack).is_dir() else None


@dataclass(slots=True)
class DetectedFace:
    bbox: tuple[int, int, int, int]
    embedding: list[float]
    det_score: float
    quality: float
    crop: np.ndarray
    gender: str | None = None  # 'male' | 'female' | None when the model is off
    age: int | None = None


class FaceEngine:
    def __init__(self) -> None:
        from insightface.app import FaceAnalysis

        # genderage is a second, small model in the same pack; skipping it when
        # the feature is off keeps the per-frame cost where it was.
        modules = ["detection", "recognition"]
        if settings.gender_detection:
            modules.append("genderage")

        kwargs = {}
        root = _model_root()
        if root is not None:
            # Without this the models are downloaded into the user's home on
            # first run — the packaged build ships them instead, so an offline
            # machine still works.
            kwargs["root"] = str(root)
            log.info("Using bundled models from %s", root / "models" / settings.model_pack)

        self.app = FaceAnalysis(
            name=settings.model_pack,
            providers=[settings.onnx_provider],
            allowed_modules=modules,
            **kwargs,
        )
        # ctx_id -1 selects CPU; any >= 0 selects that GPU device.
        ctx_id = 0 if "CUDA" in settings.onnx_provider else -1
        self.app.prepare(ctx_id=ctx_id, det_size=(settings.det_size, settings.det_size))
        log.info(
            "Face engine ready (%s, %s, gender=%s)",
            settings.model_pack,
            settings.onnx_provider,
            "on" if settings.gender_detection else "off",
        )

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

            pose = getattr(face, "pose", None)
            quality = _quality_score(crop, face.det_score, pose)
            embedding = face.normed_embedding.astype(np.float32)

            results.append(
                DetectedFace(
                    bbox=(x1, y1, width, height),
                    embedding=embedding.tolist(),
                    det_score=float(face.det_score),
                    quality=quality,
                    crop=crop,
                    gender=_gender_of(face, quality),
                    age=_age_of(face),
                )
            )

        return results


def _gender_of(face, quality: float) -> str | None:
    """Map InsightFace's binary gender output onto our labels.

    A blurry or badly lit crop is exactly where the estimate flips, so poor
    crops report nothing rather than a guess the API would then have to vote on.
    """
    gender = getattr(face, "gender", None)
    if gender is None or quality < settings.gender_min_quality:
        return None
    return "male" if int(gender) == 1 else "female"


def _age_of(face) -> int | None:
    age = getattr(face, "age", None)
    return int(age) if age is not None else None


def _safe_crop(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int, margin: float = 0.2) -> np.ndarray:
    """Crop with margin, clamped to the frame — face boxes often touch the edge."""
    height, width = frame.shape[:2]
    pad_x = int((x2 - x1) * margin)
    pad_y = int((y2 - y1) * margin)

    return frame[
        max(y1 - pad_y, 0) : min(y2 + pad_y, height),
        max(x1 - pad_x, 0) : min(x2 + pad_x, width),
    ]


def _quality_score(crop: np.ndarray, det_score: float, pose=None) -> float:
    """Combine sharpness, exposure and head angle into a 0..1 usability score.

    A blurry, badly exposed, or heavily rotated crop still yields an embedding,
    but a poor one — scoring it lets the API skip enrolling it as a reference
    vector.

    Head pose (yaw and pitch in degrees) is factored in when InsightFace
    provides it.  A frontal face scores 1.0 on the pose dimension; each degree
    beyond ``MAX_HEAD_ANGLE`` reduces the score linearly to 0.0 at twice that
    angle.
    """
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    # Variance of Laplacian: low variance means out of focus.
    sharpness = min(cv2.Laplacian(gray, cv2.CV_64F).var() / 500.0, 1.0)
    # Penalise crops that are nearly black or blown out.
    brightness = float(gray.mean()) / 255.0
    exposure = 1.0 - abs(brightness - 0.5) * 2

    # Head angle penalty using RetinaFace pose (pitch, yaw, roll in degrees).
    if pose is not None:
        try:
            pitch = float(pose[0])
            yaw = float(pose[1])
            max_angle = float(settings.max_head_angle)
            # Map [0, max_angle] → 1.0 and [max_angle, 2*max_angle] → 0.0.
            yaw_factor = max(0.0, 1.0 - max(0.0, abs(yaw) - max_angle) / max(max_angle, 1.0))
            pitch_factor = max(0.0, 1.0 - max(0.0, abs(pitch) - max_angle) / max(max_angle, 1.0))
            pose_score = yaw_factor * pitch_factor
        except (TypeError, IndexError):
            pose_score = 1.0
        return round(float(0.4 * sharpness + 0.25 * exposure + 0.15 * det_score + 0.2 * pose_score), 4)

    return round(float(0.5 * sharpness + 0.3 * exposure + 0.2 * det_score), 4)


def encode_jpeg(image: np.ndarray, quality: int = 85) -> bytes:
    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return buffer.tobytes() if ok else b""
