"""Motion-based modules: intrusion, fight, loitering, crowd, left object.

All four share one observation: a fixed camera looking at a mostly static
scene tells you a lot from pixel change alone, and that costs almost nothing
on a CPU. What separates the modules is *how* they read that change — a slow
blob appearing and staying is an abandoned bag, a violent burst of change with
several people in frame is a scuffle, a person standing still is loitering.

None of these are neural classifiers, so each one names what it actually
measured in the alert detail. An operator who sees "حرکت شدید، ۳ نفر" can
judge the footage themselves instead of trusting a label.
"""

from __future__ import annotations

import time
from datetime import datetime

import cv2
import numpy as np

from .base import Alert, AnalyticsModule, FrameContext


class _BackgroundModule(AnalyticsModule):
    """Shared background subtractor for the modules that need one."""

    def __init__(self, camera_name: str, settings: dict | None = None) -> None:
        super().__init__(camera_name, settings)
        # MOG2 with shadow detection off: shadows on a hotel floor are large
        # and would double every blob's area.
        self._background = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=32, detectShadows=False
        )
        self._frames_seen = 0

    @property
    def warming_up(self) -> bool:
        """True until the subtractor has seen enough of the empty scene.

        Its model starts empty, so the very first frames come back almost
        entirely "foreground" — without this, every camera would raise an
        alarm the moment the service starts.
        """
        return self._frames_seen < int(self.settings.get("warmup_frames", 30))

    def foreground(self, frame: np.ndarray) -> np.ndarray:
        self._frames_seen += 1
        mask = self._background.apply(frame)
        # Opening removes sensor speckle; dilation reconnects a person split
        # into two blobs by a dark jacket.
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        return cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=2)

    @staticmethod
    def changed_fraction(mask: np.ndarray) -> float:
        return float(np.count_nonzero(mask)) / mask.size


class IntrusionModule(_BackgroundModule):
    """Movement inside a zone that should be empty."""

    id = "intrusion"
    defaults = {
        "min_area_percent": 1.5,
        "zone": [],
        "active_hours": [],
        "warmup_frames": 30,
        "cooldown_seconds": 60,
    }

    def process(self, context: FrameContext) -> Alert | None:
        if not self._within_active_hours() or not self.cooled_down():
            return None

        mask = self.foreground(context.frame)
        if self.warming_up:
            return None

        zone = self.settings.get("zone") or []
        if zone:
            mask = cv2.bitwise_and(mask, _zone_mask(mask.shape, zone))

        percent = self.changed_fraction(mask) * 100
        if percent < float(self.settings["min_area_percent"]):
            return None

        alert = self.alert(
            f"ورود به منطقهٔ ممنوعه — {self.camera_name}",
            changed_percent=round(percent, 2),
            zone_limited=bool(zone),
        )
        alert.severity = "critical"
        alert.frame = context.frame
        return alert

    def _within_active_hours(self) -> bool:
        windows = self.settings.get("active_hours") or []
        if not windows:
            return True

        hour = datetime.now().hour
        for start, end in windows:
            # A window may wrap past midnight, e.g. 22 → 6.
            if start <= end:
                if start <= hour < end:
                    return True
            elif hour >= start or hour < end:
                return True
        return False


class FightModule(_BackgroundModule):
    """Sudden violent motion with several people close together.

    Deliberately conservative: the alert needs the motion burst to *persist*
    for a few seconds, because a single frame of someone walking past the lens
    looks identical to a shove.
    """

    id = "fight"
    defaults = {
        "motion_threshold": 0.045,
        "min_people": 2,
        "sustain_seconds": 3,
        "warmup_frames": 30,
        "cooldown_seconds": 120,
    }

    def __init__(self, camera_name: str, settings: dict | None = None) -> None:
        super().__init__(camera_name, settings)
        self._agitated_since: float | None = None
        self._peak = 0.0

    def process(self, context: FrameContext) -> Alert | None:
        people = len(context.faces)
        motion = self.changed_fraction(self.foreground(context.frame))
        if self.warming_up:
            return None

        agitated = (
            motion >= float(self.settings["motion_threshold"])
            and people >= int(self.settings["min_people"])
        )

        if not agitated:
            self._agitated_since = None
            self._peak = 0.0
            return None

        now = time.monotonic()
        self._peak = max(self._peak, motion)
        if self._agitated_since is None:
            self._agitated_since = now
            return None

        if now - self._agitated_since < float(self.settings["sustain_seconds"]):
            return None
        if not self.cooled_down():
            return None

        alert = self.alert(
            f"احتمال درگیری — {self.camera_name}",
            motion_percent=round(self._peak * 100, 2),
            people=people,
            sustained_seconds=round(now - self._agitated_since, 1),
        )
        alert.severity = "critical"
        alert.frame = context.frame
        self._agitated_since = None
        return alert


class CrowdModule(AnalyticsModule):
    """More people in frame than the room should hold."""

    id = "crowd"
    defaults = {"max_people": 5, "sustain_seconds": 10, "cooldown_seconds": 120}

    def __init__(self, camera_name: str, settings: dict | None = None) -> None:
        super().__init__(camera_name, settings)
        self._crowded_since: float | None = None

    def process(self, context: FrameContext) -> Alert | None:
        people = len(context.faces)
        if people <= int(self.settings["max_people"]):
            self._crowded_since = None
            return None

        now = time.monotonic()
        if self._crowded_since is None:
            self._crowded_since = now
            return None
        if now - self._crowded_since < float(self.settings["sustain_seconds"]):
            return None
        if not self.cooled_down():
            return None

        alert = self.alert(f"تجمع غیرعادی — {self.camera_name}", people=people)
        alert.frame = context.frame
        self._crowded_since = None
        return alert


class LoiteringModule(AnalyticsModule):
    """Somebody who has not moved on.

    Tracked by face position rather than identity: two people standing a metre
    apart keep separate timers, and a face that drifts across the frame resets
    its own.
    """

    id = "loitering"
    defaults = {"seconds": 180, "cooldown_seconds": 300}
    #: how far (in pixels) a face may drift and still count as the same spot
    TOLERANCE = 90

    def __init__(self, camera_name: str, settings: dict | None = None) -> None:
        super().__init__(camera_name, settings)
        self._seen_since: dict[tuple[int, int], float] = {}

    def process(self, context: FrameContext) -> Alert | None:
        now = time.monotonic()
        limit = float(self.settings["seconds"])
        current: dict[tuple[int, int], float] = {}
        longest = 0.0

        for x, y, w, h in context.faces:
            centre = (x + w // 2, y + h // 2)
            key = self._match(centre)
            since = self._seen_since.get(key, now) if key else now
            current[key or centre] = since
            longest = max(longest, now - since)

        self._seen_since = current

        if longest < limit or not self.cooled_down():
            return None

        alert = self.alert(
            f"پرسه‌زنی — {self.camera_name}",
            minutes=round(longest / 60, 1),
        )
        alert.frame = context.frame
        return alert

    def _match(self, centre: tuple[int, int]) -> tuple[int, int] | None:
        """Find an already-tracked spot close enough to be the same person."""
        for known in self._seen_since:
            if abs(known[0] - centre[0]) <= self.TOLERANCE and abs(known[1] - centre[1]) <= self.TOLERANCE:
                return known
        return None


class ObjectLeftModule(_BackgroundModule):
    """A blob that appeared and then stopped changing — or vanished.

    Covers both halves of the same question: a bag left behind in the lobby,
    and something lifted from a place it always occupied.
    """

    id = "object_left"
    defaults = {"seconds": 45, "min_area_percent": 0.5, "cooldown_seconds": 180}

    def __init__(self, camera_name: str, settings: dict | None = None) -> None:
        super().__init__(camera_name, settings)
        self._reference: np.ndarray | None = None
        self._stable_since: float | None = None

    def process(self, context: FrameContext) -> Alert | None:
        grey = cv2.cvtColor(context.frame, cv2.COLOR_BGR2GRAY)
        grey = cv2.GaussianBlur(grey, (21, 21), 0)

        if self._reference is None:
            self._reference = grey
            return None

        difference = cv2.absdiff(self._reference, grey)
        changed = cv2.threshold(difference, 30, 255, cv2.THRESH_BINARY)[1]
        percent = self.changed_fraction(changed) * 100

        # People walking through keep the frame busy; only a persistent change
        # against the reference counts.
        if percent < float(self.settings["min_area_percent"]) or context.faces:
            self._stable_since = None
            # Nothing standing out: adopt the current view as the new normal.
            self._reference = cv2.addWeighted(self._reference, 0.9, grey, 0.1, 0)
            return None

        now = time.monotonic()
        if self._stable_since is None:
            self._stable_since = now
            return None
        if now - self._stable_since < float(self.settings["seconds"]) or not self.cooled_down():
            return None

        alert = self.alert(
            f"شیء جاگذاشته یا برداشته‌شده — {self.camera_name}",
            changed_percent=round(percent, 2),
            still_for_seconds=round(now - self._stable_since),
        )
        alert.frame = context.frame
        self._reference = grey
        self._stable_since = None
        return alert


def _zone_mask(shape: tuple[int, ...], polygon: list) -> np.ndarray:
    """Turn normalised polygon points into a pixel mask."""
    height, width = shape[:2]
    points = np.array(
        [[int(x * width), int(y * height)] for x, y in polygon], dtype=np.int32
    )
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(mask, [points], 255)
    return mask
