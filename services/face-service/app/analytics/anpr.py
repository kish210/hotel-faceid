"""Licence-plate reading.

Unlike the motion modules this one needs a real model, which is why it is
pack-backed: the admin page downloads `plate_detector.onnx` (and an optional
character recogniser) into `data/modules/anpr/` and only then does the module
start. Until the pack is there the module reports itself unavailable and the
worker skips it, rather than the camera silently doing nothing.

The detector runs on ONNXRuntime — already a dependency for face recognition —
so no extra package is installed. It is deliberately given a low frame rate by
the worker: plate reading is the heaviest thing this server does.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import cv2
import numpy as np

from ..config import settings
from .base import Alert, AnalyticsModule, FrameContext

log = logging.getLogger(__name__)

DETECTOR_FILE = "plate_detector.onnx"
RECOGNISER_FILE = "plate_ocr.onnx"

# Iranian plates read as two digits, a letter, three digits and a two-digit
# region code. Kept loose so a partially-read plate is still reported.
PLATE_PATTERN = re.compile(r"^[0-9]{2}[A-Za-z؀-ۿ]?[0-9]{3}[0-9]{0,2}$")


def pack_dir() -> Path:
    """Where the admin page puts the downloaded pack."""
    if settings.module_root:
        return Path(settings.module_root) / "anpr"
    return Path("data/modules/anpr")


def is_available() -> bool:
    return (pack_dir() / DETECTOR_FILE).is_file()


class AnprModule(AnalyticsModule):
    id = "anpr"
    defaults = {"min_confidence": 0.55, "cooldown_seconds": 20}
    #: plates are square-ish to wide; anything outside this is not a plate
    MIN_ASPECT = 2.0
    MAX_ASPECT = 6.0

    def __init__(self, camera_name: str, settings_override: dict | None = None) -> None:
        super().__init__(camera_name, settings_override)
        self._detector: cv2.dnn.Net | None = None
        self._last_plate: str | None = None

    def _load(self) -> cv2.dnn.Net | None:
        if self._detector is not None:
            return self._detector
        model = pack_dir() / DETECTOR_FILE
        if not model.is_file():
            return None
        try:
            self._detector = cv2.dnn.readNetFromONNX(str(model))
        except cv2.error:
            log.warning("Plate model at %s could not be loaded", model, exc_info=True)
            return None
        return self._detector

    def process(self, context: FrameContext) -> Alert | None:
        if not self.cooled_down():
            return None

        detector = self._load()
        if detector is None:
            return None

        boxes = self._detect(detector, context.frame)
        if not boxes:
            return None

        # The largest candidate is the closest vehicle, which is the one
        # entering or leaving.
        x, y, w, h = max(boxes, key=lambda box: box[2] * box[3])
        crop = context.frame[max(y, 0) : y + h, max(x, 0) : x + w]
        if crop.size == 0:
            return None

        text = _read_characters(crop)
        if text is None:
            return None

        # A car waiting at a barrier is seen for many frames; only report a
        # plate once until a different one shows up.
        if text == self._last_plate:
            return None
        self._last_plate = text

        alert = self.alert(f"پلاک خودرو — {self.camera_name}", plate=text)
        alert.severity = "info"
        alert.frame = crop
        return alert

    def _detect(self, detector: cv2.dnn.Net, frame: np.ndarray) -> list[tuple[int, int, int, int]]:
        height, width = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (640, 640), swapRB=True, crop=False)
        detector.setInput(blob)

        try:
            raw = detector.forward()
        except cv2.error:
            log.warning("Plate detection failed on %s", self.camera_name, exc_info=True)
            return []

        # YOLO-style output: (1, N, 5+) rows of cx, cy, w, h, confidence.
        rows = raw[0] if raw.ndim == 3 else raw
        threshold = float(self.settings["min_confidence"])
        scale_x, scale_y = width / 640, height / 640

        boxes: list[tuple[int, int, int, int]] = []
        for row in rows:
            if len(row) < 5 or float(row[4]) < threshold:
                continue
            cx, cy, bw, bh = (float(v) for v in row[:4])
            box_w, box_h = bw * scale_x, bh * scale_y
            if box_h <= 0:
                continue
            aspect = box_w / box_h
            if not (self.MIN_ASPECT <= aspect <= self.MAX_ASPECT):
                continue
            boxes.append(
                (int((cx * scale_x) - box_w / 2), int((cy * scale_y) - box_h / 2), int(box_w), int(box_h))
            )
        return boxes


def _read_characters(crop: np.ndarray) -> str | None:
    """Turn a plate crop into text.

    The pack ships a character model when one is available; without it the
    plate is still reported as a snapshot with no text, which is what the
    barrier operator mostly needs. Returning None means "not even a plate".
    """
    model = pack_dir() / RECOGNISER_FILE
    if not model.is_file():
        return ""  # no OCR installed: the alert carries the image only

    grey = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    grey = cv2.resize(grey, (192, 64))
    blob = cv2.dnn.blobFromImage(grey, 1 / 255.0)

    try:
        network = cv2.dnn.readNetFromONNX(str(model))
        network.setInput(blob)
        output = network.forward()
    except cv2.error:
        log.warning("Plate OCR failed", exc_info=True)
        return ""

    text = _decode(output)
    return text if text and PLATE_PATTERN.match(text) else text or ""


def _decode(output: np.ndarray) -> str:
    """Greedy CTC decode over the recogniser's per-position class scores."""
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    sequence = output[0] if output.ndim == 3 else output

    characters: list[str] = []
    previous = -1
    for position in sequence:
        index = int(np.argmax(position))
        # CTC: class 0 is the blank, and a repeat of the previous class is the
        # same character held across two positions.
        if index != previous and 0 < index <= len(alphabet):
            characters.append(alphabet[index - 1])
        previous = index
    return "".join(characters)
