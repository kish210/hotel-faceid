"""Analytics module behaviour, driven by synthetic frames.

Each test builds the situation the module is supposed to notice and checks it
fires — and, just as importantly, that a quiet scene does not.
"""

import time

import numpy as np

from app.analytics import build_pipeline
from app.analytics.base import FrameContext
from app.analytics.motion import (
    CrowdModule,
    FightModule,
    IntrusionModule,
    LoiteringModule,
)


# Ten frames is plenty to learn a synthetic scene; a real camera uses 30.
WARM = {"warmup_frames": 10}


def blank(value=30):
    return np.full((240, 320, 3), value, dtype=np.uint8)


def with_blob(size=140, value=230):
    """A frame with a large bright rectangle — a person walking in."""
    frame = blank()
    frame[40 : 40 + size, 40 : 40 + size] = value
    return frame


def feed(module, frame, faces=(), times=1):
    """Push a frame through a module, returning the first alert it raises.

    Returning the *first* rather than the last matters: a module that fires and
    then correctly suppresses its repeats would otherwise look silent.
    """
    for _ in range(times):
        alert = module.process(FrameContext(frame=frame, faces=list(faces)))
        if alert is not None:
            return alert
    return None


# ------------------------------------------------------------- intrusion
def test_intrusion_ignores_static_scene():
    module = IntrusionModule("cam", WARM)
    assert feed(module, blank(), times=40) is None


def test_intrusion_fires_on_large_change():
    module = IntrusionModule("cam", WARM)
    feed(module, blank(), times=15)  # learn the empty room
    alert = feed(module, with_blob(), times=3)
    assert alert is not None, "a large moving blob should raise an intrusion"
    assert alert.severity == "critical"
    assert alert.detail["changed_percent"] > 0


def test_intrusion_respects_active_hours():
    # A window that cannot contain the current hour keeps the module quiet.
    hour = time.localtime().tm_hour
    dead = [[(hour + 2) % 24, (hour + 3) % 24]]
    module = IntrusionModule("cam", {**WARM, "active_hours": dead})
    feed(module, blank(), times=15)
    assert feed(module, with_blob(), times=3) is None


def test_intrusion_cooldown_suppresses_repeats():
    module = IntrusionModule("cam", {**WARM, "cooldown_seconds": 300})
    feed(module, blank(), times=15)
    assert feed(module, with_blob(), times=3) is not None
    assert feed(module, with_blob(), times=3) is None, "cooldown should hold"


# ----------------------------------------------------------------- crowd
def test_crowd_needs_sustained_presence():
    module = CrowdModule("cam", {"max_people": 2, "sustain_seconds": 0.2})
    faces = [(0, 0, 10, 10)] * 5
    assert feed(module, blank(), faces) is None, "first sighting only starts the timer"
    time.sleep(0.25)
    alert = feed(module, blank(), faces)
    assert alert is not None and alert.detail["people"] == 5


def test_crowd_quiet_below_limit():
    module = CrowdModule("cam", {"max_people": 5})
    assert feed(module, blank(), [(0, 0, 10, 10)] * 3, times=5) is None


# ----------------------------------------------------------------- fight
def test_fight_needs_motion_and_people():
    module = FightModule("cam", {**WARM, "sustain_seconds": 0.2, "motion_threshold": 0.02})
    faces = [(0, 0, 10, 10), (60, 60, 10, 10)]

    feed(module, blank(), faces, times=10)
    # Motion alone is not enough on the first frame — it must persist.
    assert feed(module, with_blob(), faces) is None
    time.sleep(0.25)
    alert = feed(module, with_blob(200), faces)
    assert alert is not None, "sustained motion with two people is a fight signal"
    assert alert.detail["people"] == 2


def test_fight_ignores_motion_from_one_person():
    module = FightModule("cam", {**WARM, "sustain_seconds": 0.1})
    feed(module, blank(), times=10)
    time.sleep(0.15)
    assert feed(module, with_blob(200), [(0, 0, 10, 10)], times=3) is None


# ------------------------------------------------------------- loitering
def test_loitering_fires_after_the_limit():
    module = LoiteringModule("cam", {"seconds": 0.2})
    face = [(100, 100, 40, 40)]
    assert feed(module, blank(), face) is None
    time.sleep(0.25)
    alert = feed(module, blank(), face)
    assert alert is not None and alert.detail["minutes"] >= 0


def test_loitering_resets_when_the_spot_empties():
    module = LoiteringModule("cam", {"seconds": 0.2})
    feed(module, blank(), [(100, 100, 40, 40)])
    time.sleep(0.25)
    feed(module, blank(), [])  # they left
    assert feed(module, blank(), [(100, 100, 40, 40)]) is None


# -------------------------------------------------------------- pipeline
def test_pipeline_builds_known_modules_only():
    pipeline = build_pipeline("cam", ["fight", "does-not-exist"], {})
    assert [module.id for module in pipeline] == ["fight"]


def test_pipeline_skips_modules_without_their_pack():
    # anpr needs a downloaded model; it must not be built without one.
    assert build_pipeline("cam", ["anpr"], {}) == []


def test_pipeline_passes_settings_through():
    pipeline = build_pipeline("cam", ["crowd"], {"crowd": {"max_people": 9}})
    assert pipeline[0].settings["max_people"] == 9
    assert pipeline[0].settings["cooldown_seconds"] == 120, "defaults still apply"


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
            print(f"  ok  {name}")
    print("ALL ANALYTICS TESTS PASSED")
