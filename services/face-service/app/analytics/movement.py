"""Modules that follow where people go, rather than how much the frame changes.

Both of these work from the face boxes the recogniser has already produced, so
they cost almost nothing: the expensive part of the frame was paid for once,
and this is arithmetic on a handful of rectangles.

The tracking is deliberately simple — nearest box between consecutive frames,
within a distance a person could plausibly cover. It is enough to tell running
from walking, and to tell which way somebody went through a doorway. It is not
enough to follow one guest across a crowded lobby, and nothing here pretends
otherwise.
"""

from __future__ import annotations

import time

from .base import Alert, AnalyticsModule, FrameContext

Point = tuple[float, float]


def _centre(box: tuple[int, int, int, int]) -> tuple[int, int]:
    x, y, w, h = box
    return x + w // 2, y + h // 2


class _Tracker:
    """Match this frame's faces to the previous frame's, by proximity.

    How far a face may jump and still count as the same person depends on what
    the caller is asking. Analytics sees only a fraction of the frames, so at a
    doorway somebody can cross half the picture between two looks — a counter
    that insisted on small steps would simply miss them. A speed measurement
    wants the opposite: pair two strangers and it invents a sprint.
    """

    def __init__(self, max_step: float = 0.35) -> None:
        self.max_step = max_step
        self.previous: list[tuple[int, int]] = []

    def pair(self, centres: list[tuple[int, int]], width: int) -> list[tuple[tuple, tuple]]:
        """Return (previous, current) pairs for faces that look like the same person."""
        limit = width * self.max_step
        pairs: list[tuple[tuple, tuple]] = []
        unclaimed = list(self.previous)

        for centre in centres:
            best = None
            best_distance = limit
            for candidate in unclaimed:
                distance = ((candidate[0] - centre[0]) ** 2 + (candidate[1] - centre[1]) ** 2) ** 0.5
                if distance < best_distance:
                    best, best_distance = candidate, distance
            if best is not None:
                unclaimed.remove(best)
                pairs.append((best, centre))

        self.previous = centres
        return pairs


class RunningModule(AnalyticsModule):
    """Somebody moving far faster than a walk.

    Speed is measured as a fraction of the frame width per frame, so it does
    not depend on how far the camera is from the corridor.
    """

    id = "running"
    defaults = {"speed_threshold": 0.22, "min_frames": 2, "max_step": 0.35, "cooldown_seconds": 90}

    def __init__(self, camera_name: str, settings: dict | None = None) -> None:
        super().__init__(camera_name, settings)
        # Deliberately tight: a pairing beyond this is more likely two people
        # than one fast one, and that would be reported as a sprint.
        self._tracker = _Tracker(float(self.settings["max_step"]))
        self._fast_frames = 0

    def process(self, context: FrameContext) -> Alert | None:
        width = context.frame.shape[1]
        centres = [_centre(box) for box in context.faces]
        fastest = 0.0

        for previous, current in self._tracker.pair(centres, width):
            distance = ((current[0] - previous[0]) ** 2 + (current[1] - previous[1]) ** 2) ** 0.5
            fastest = max(fastest, distance / width)

        if fastest < float(self.settings["speed_threshold"]):
            self._fast_frames = 0
            return None

        self._fast_frames += 1
        if self._fast_frames < int(self.settings["min_frames"]) or not self.cooled_down():
            return None

        alert = self.alert(
            f"حرکت سریع / دویدن — {self.camera_name}",
            speed_percent_of_frame=round(fastest * 100, 1),
            people=len(centres),
        )
        alert.frame = context.frame
        self._fast_frames = 0
        return alert


class LineCrossModule(AnalyticsModule):
    """Count people crossing a line, and say which way they went.

    The line is given in fractions of the frame, so it survives a resolution
    change: [[0, 0.5], [1, 0.5]] is a horizontal line across the middle.
    """

    id = "line_cross"
    defaults = {"line": [[0.0, 0.5], [1.0, 0.5]], "max_step": 0.6, "cooldown_seconds": 5}

    def __init__(self, camera_name: str, settings: dict | None = None) -> None:
        super().__init__(camera_name, settings)
        # Generous: missing a crossing is worse than counting a near-miss, and
        # analytics only sees a fraction of the frames.
        self._tracker = _Tracker(float(self.settings["max_step"]))
        self._counts = {"forward": 0, "backward": 0}

    def process(self, context: FrameContext) -> Alert | None:
        height, width = context.frame.shape[:2]
        (x1, y1), (x2, y2) = (
            (p[0] * width, p[1] * height) for p in self.settings["line"]
        )

        centres = [_centre(box) for box in context.faces]
        crossed: str | None = None

        for previous, current in self._tracker.pair(centres, width):
            before = _side(previous, (x1, y1), (x2, y2))
            after = _side(current, (x1, y1), (x2, y2))
            if before == 0 or after == 0 or before == after:
                continue
            crossed = "forward" if after > 0 else "backward"
            self._counts[crossed] += 1

        if crossed is None or not self.cooled_down():
            return None

        direction = "رفت" if crossed == "forward" else "برگشت"
        alert = self.alert(
            f"عبور از خط ({direction}) — {self.camera_name}",
            direction=crossed,
            forward_total=self._counts["forward"],
            backward_total=self._counts["backward"],
        )
        alert.severity = "info"
        alert.frame = context.frame
        return alert


def _side(point: tuple[int, int], start: Point, end: Point) -> int:
    """Which side of the line the point is on: +1, -1, or 0 when exactly on it."""
    cross = (end[0] - start[0]) * (point[1] - start[1]) - (end[1] - start[1]) * (point[0] - start[0])
    if cross > 1e-6:
        return 1
    if cross < -1e-6:
        return -1
    return 0
