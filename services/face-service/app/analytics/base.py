"""Contract every analytics module implements.

A module receives sampled frames from one camera and returns alerts. It owns
whatever state it needs between frames (background model, timers, counters),
so one instance belongs to exactly one camera and is never shared.

Modules run on the plain CPU: the hotel server has no GPU, and a module that
cannot keep up would starve face recognition, which is the primary job. That
budget is why the built-in modules are motion- and geometry-based rather than
neural, and why each one declares a cooldown instead of alerting per frame.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(slots=True)
class Alert:
    """Something worth showing an operator."""

    module: str
    title: str
    severity: str = "warning"  # info | warning | critical
    detail: dict[str, Any] = field(default_factory=dict)
    #: frame to attach; the worker encodes it
    frame: np.ndarray | None = None


@dataclass(slots=True)
class FrameContext:
    """What the worker knows about the frame it is handing over."""

    frame: np.ndarray
    #: face boxes already found by the recogniser, as (x, y, w, h)
    faces: list[tuple[int, int, int, int]] = field(default_factory=list)


class AnalyticsModule(ABC):
    #: value stored in `cameras.analytics`
    id: str = "base"
    #: display name, mirrored from the API catalogue for log messages
    name: str = ""
    #: defaults merged with the per-camera overrides
    defaults: dict[str, Any] = {}

    def __init__(self, camera_name: str, settings: dict[str, Any] | None = None) -> None:
        self.camera_name = camera_name
        self.settings = {**self.defaults, **(settings or {})}
        self._last_alert_at = 0.0

    @abstractmethod
    def process(self, context: FrameContext) -> Alert | None:
        """Look at one frame and decide whether to raise an alert."""

    # ------------------------------------------------------------- helpers
    def cooled_down(self) -> bool:
        """True when enough time has passed since the last alert.

        Every module needs this: a fight lasts many frames and a parked car
        stays parked, and neither should produce an alert per frame.
        """
        cooldown = float(self.settings.get("cooldown_seconds", 60))
        return (time.monotonic() - self._last_alert_at) >= cooldown

    def mark_alerted(self) -> None:
        self._last_alert_at = time.monotonic()

    def alert(self, title: str, **detail: Any) -> Alert:
        self.mark_alerted()
        return Alert(module=self.id, title=title, detail=detail)
