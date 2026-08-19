"""Modules that watch the camera rather than the people in front of it.

A camera that has been turned to face the ceiling, sprayed, knocked out of
focus or blinded by a lamp keeps streaming perfectly valid frames. Nothing
downstream notices: recognition simply stops finding faces, which looks
identical to a quiet corridor. These three modules close that gap, and they
are the cheapest ones here — each is a couple of statistics over one frame.

All of them insist the condition *persists* before alerting: somebody walking
past the lens, a door opening onto sunlight, or a camera's own auto-exposure
hunting all produce a second or two of exactly these symptoms.
"""

from __future__ import annotations

import time

import cv2
import numpy as np

from .base import Alert, AnalyticsModule, FrameContext


class _SustainedCondition(AnalyticsModule):
    """Shared timing for "true for N seconds before it counts"."""

    def __init__(self, camera_name: str, settings: dict | None = None) -> None:
        super().__init__(camera_name, settings)
        self._since: float | None = None

    def sustained(self, condition: bool) -> float | None:
        """Seconds the condition has held, or None if not long enough yet."""
        if not condition:
            self._since = None
            return None

        now = time.monotonic()
        if self._since is None:
            self._since = now
            return None

        held = now - self._since
        return held if held >= float(self.settings["sustain_seconds"]) else None

    def clear(self) -> None:
        self._since = None


class TamperModule(_SustainedCondition):
    """The view changed wholesale and stayed changed.

    Distinguished from ordinary movement by *how much* of the frame differs:
    a person crossing the lens changes part of it for a moment, a bag over the
    camera changes nearly all of it for good.
    """

    id = "tamper"
    defaults = {"change_threshold": 0.7, "sustain_seconds": 5, "cooldown_seconds": 300}

    def __init__(self, camera_name: str, settings: dict | None = None) -> None:
        super().__init__(camera_name, settings)
        self._reference: np.ndarray | None = None

    def process(self, context: FrameContext) -> Alert | None:
        small = _thumbnail(context.frame)

        if self._reference is None:
            self._reference = small
            return None

        difference = cv2.absdiff(self._reference, small)
        changed = float(np.count_nonzero(difference > 45)) / difference.size

        held = self.sustained(changed >= float(self.settings["change_threshold"]))
        if held is None:
            # Drift with the scene so daylight turning to dusk is not tampering.
            self._reference = cv2.addWeighted(self._reference, 0.98, small, 0.02, 0)
            return None
        if not self.cooled_down():
            return None

        alert = self.alert(
            f"دستکاری یا پوشاندن دوربین — {self.camera_name}",
            changed_percent=round(changed * 100, 1),
            seconds=round(held),
        )
        alert.severity = "critical"
        alert.frame = context.frame
        # Adopt the new view: the camera may simply have been re-aimed on purpose.
        self._reference = small
        self.clear()
        return alert


class DefocusModule(_SustainedCondition):
    """The picture went soft — knocked out of focus, or a dirty lens."""

    id = "defocus"
    defaults = {
        "sharpness_threshold": 45.0,
        "sustain_seconds": 30,
        "cooldown_seconds": 1800,
    }

    def process(self, context: FrameContext) -> Alert | None:
        grey = cv2.cvtColor(_thumbnail(context.frame, 320), cv2.COLOR_BGR2GRAY)
        # Variance of the Laplacian: the standard focus measure. A sharp frame
        # has strong edges and therefore high variance.
        sharpness = float(cv2.Laplacian(grey, cv2.CV_64F).var())

        held = self.sustained(sharpness < float(self.settings["sharpness_threshold"]))
        if held is None or not self.cooled_down():
            return None

        alert = self.alert(
            f"تصویر تار شده — {self.camera_name}",
            sharpness=round(sharpness, 1),
            seconds=round(held),
        )
        alert.severity = "warning"
        alert.frame = context.frame
        self.clear()
        return alert


class BlackoutModule(_SustainedCondition):
    """The frame carries no picture: black, white, or a flat grey wash."""

    id = "blackout"
    defaults = {"sustain_seconds": 20, "cooldown_seconds": 900}
    #: below this spread of pixel values there is nothing to see
    FLAT_STDDEV = 6.0
    DARK_MEAN = 18.0
    BRIGHT_MEAN = 240.0

    def process(self, context: FrameContext) -> Alert | None:
        grey = cv2.cvtColor(_thumbnail(context.frame, 160), cv2.COLOR_BGR2GRAY)
        mean, stddev = (float(v) for v in cv2.meanStdDev(grey))

        blind = stddev < self.FLAT_STDDEV or mean < self.DARK_MEAN or mean > self.BRIGHT_MEAN
        held = self.sustained(blind)
        if held is None or not self.cooled_down():
            return None

        if mean < self.DARK_MEAN:
            reason = "تصویر کاملاً تاریک است"
        elif mean > self.BRIGHT_MEAN:
            reason = "نور شدید مقابل لنز"
        else:
            reason = "تصویر یکنواخت و بدون جزئیات"

        alert = self.alert(
            f"تصویر دوربین از بین رفته — {self.camera_name}",
            reason=reason,
            brightness=round(mean, 1),
            contrast=round(stddev, 1),
            seconds=round(held),
        )
        alert.severity = "critical"
        alert.frame = context.frame
        self.clear()
        return alert


def _thumbnail(frame: np.ndarray, width: int = 240) -> np.ndarray:
    """Shrink before measuring: these statistics do not need the full frame,
    and the smaller image is what keeps these modules nearly free."""
    height = max(int(frame.shape[0] * (width / frame.shape[1])), 1)
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
