"""Early smoke and flame warning.

Flame has a narrow colour signature and, crucially, never holds still: a fire
flickers many times a second while a red carpet or an orange lamp does not.
Smoke is the opposite — grey, low-saturation, and it *grows* rather than
moving across the frame the way a person does.

This is a heuristic, and it says so in every alert it raises. It is worth
having because it costs almost nothing and can notice a bin fire in a corridor
minutes before anyone walks past — but it does not replace a smoke detector,
and the module description in the panel says exactly that.
"""

from __future__ import annotations

import time

import cv2
import numpy as np

from .base import Alert, AnalyticsModule, FrameContext

# Flame in HSV: red-orange-yellow hues, strongly saturated, bright.
FLAME_LOW = np.array([0, 90, 170], dtype=np.uint8)
FLAME_HIGH = np.array([35, 255, 255], dtype=np.uint8)
# Smoke: almost no colour, mid brightness.
SMOKE_LOW = np.array([0, 0, 70], dtype=np.uint8)
SMOKE_HIGH = np.array([180, 45, 200], dtype=np.uint8)


class SmokeFireModule(AnalyticsModule):
    id = "smoke_fire"
    defaults = {
        "min_area_percent": 0.8,
        "sustain_seconds": 6,
        "warmup_frames": 30,
        "cooldown_seconds": 300,
    }

    def __init__(self, camera_name: str, settings: dict | None = None) -> None:
        super().__init__(camera_name, settings)
        self._background = cv2.createBackgroundSubtractorMOG2(
            history=300, varThreshold=24, detectShadows=False
        )
        self._frames_seen = 0
        self._candidate_since: float | None = None
        self._peak = 0.0
        self._kind = ""

    def process(self, context: FrameContext) -> Alert | None:
        self._frames_seen += 1
        moving = self._background.apply(context.frame)
        if self._frames_seen < int(self.settings.get("warmup_frames", 30)):
            return None

        hsv = cv2.cvtColor(context.frame, cv2.COLOR_BGR2HSV)
        flame = cv2.inRange(hsv, FLAME_LOW, FLAME_HIGH)
        smoke = cv2.inRange(hsv, SMOKE_LOW, SMOKE_HIGH)

        # The colour must also be *changing*: a static orange sofa is not a
        # fire, and a grey wall is not smoke.
        flame_area = self._fraction(cv2.bitwise_and(flame, moving))
        smoke_area = self._fraction(cv2.bitwise_and(smoke, moving))

        threshold = float(self.settings["min_area_percent"]) / 100
        if flame_area >= threshold:
            kind, area = "آتش", flame_area
        elif smoke_area >= threshold * 2:  # smoke needs a bigger patch to count
            kind, area = "دود", smoke_area
        else:
            self._candidate_since = None
            self._peak = 0.0
            return None

        now = time.monotonic()
        self._peak = max(self._peak, area)
        self._kind = kind
        if self._candidate_since is None:
            self._candidate_since = now
            return None
        if now - self._candidate_since < float(self.settings["sustain_seconds"]):
            return None
        if not self.cooled_down():
            return None

        alert = self.alert(
            f"احتمال {self._kind} — {self.camera_name}",
            kind=self._kind,
            area_percent=round(self._peak * 100, 2),
            sustained_seconds=round(now - self._candidate_since, 1),
            note="تشخیص بر پایهٔ رنگ و حرکت است؛ جای دتکتور دود را نمی‌گیرد",
        )
        alert.severity = "critical"
        alert.frame = context.frame
        self._candidate_since = None
        return alert

    @staticmethod
    def _fraction(mask: np.ndarray) -> float:
        return float(np.count_nonzero(mask)) / mask.size
