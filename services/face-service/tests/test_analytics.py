"""Analytics module behaviour, driven by synthetic frames.

Each test builds the situation the module is supposed to notice and checks it
fires — and, just as importantly, that a quiet scene does not.
"""

import time

import numpy as np

from app.analytics import build_pipeline
from app.analytics.base import FrameContext
from app.analytics.fire import SmokeFireModule
from app.analytics.motion import (
    CrowdModule,
    FightModule,
    IntrusionModule,
    LoiteringModule,
)
from app.analytics.movement import LineCrossModule, RunningModule
from app.analytics.scene import BlackoutModule, DefocusModule, TamperModule


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


# ------------------------------------------------------------ camera health
def test_tamper_fires_when_the_view_is_covered():
    module = TamperModule("cam", {"sustain_seconds": 0.2, "change_threshold": 0.5})
    feed(module, blank(), times=3)  # learn the room
    covered = blank(240)  # something bright held over the lens

    assert feed(module, covered) is None, "one frame is not tampering"
    time.sleep(0.25)
    alert = feed(module, covered)
    assert alert is not None and alert.severity == "critical"


def test_tamper_ignores_a_stable_scene():
    module = TamperModule("cam", {"sustain_seconds": 0.1})
    assert feed(module, blank(), times=20) is None


def test_defocus_fires_on_a_flat_image():
    module = DefocusModule("cam", {"sustain_seconds": 0.2, "sharpness_threshold": 20.0})
    assert feed(module, blank()) is None
    time.sleep(0.25)
    alert = feed(module, blank())
    assert alert is not None and alert.detail["sharpness"] < 20.0


def test_defocus_quiet_on_a_sharp_image():
    module = DefocusModule("cam", {"sustain_seconds": 0.1, "sharpness_threshold": 20.0})
    detailed = np.random.default_rng(7).integers(0, 255, (240, 320, 3), dtype=np.uint8)
    feed(module, detailed)
    time.sleep(0.15)
    assert feed(module, detailed) is None, "a detailed image is in focus"


def test_blackout_fires_on_a_dark_frame():
    module = BlackoutModule("cam", {"sustain_seconds": 0.2})
    dark = blank(3)
    assert feed(module, dark) is None
    time.sleep(0.25)
    alert = feed(module, dark)
    assert alert is not None and "تاریک" in alert.detail["reason"]


# ------------------------------------------------------------- smoke / fire
def flickering_flame(step):
    """Orange, and never twice the same — which is what marks it as fire.

    A rectangle that holds perfectly still gets absorbed into the background
    within a frame or two, exactly as a painted wall should be.
    """
    frame = blank()
    top = 60 + (step % 3) * 6
    frame[top : top + 120, 60:220] = (20, 140 + (step % 2) * 40, 250)  # BGR orange
    return frame


def test_smoke_fire_needs_moving_flame_colour():
    module = SmokeFireModule(
        "cam", {"warmup_frames": 3, "sustain_seconds": 0.2, "min_area_percent": 0.5}
    )
    feed(module, blank(), times=5)

    assert feed(module, flickering_flame(0)) is None, "first sighting only starts the timer"
    time.sleep(0.25)

    alert = None
    for step in range(1, 6):
        alert = module.process(FrameContext(frame=flickering_flame(step), faces=[]))
        if alert is not None:
            break
    assert alert is not None, "sustained flickering flame colour should alert"
    assert alert.detail["kind"] == "آتش" and alert.severity == "critical"


def test_smoke_fire_ignores_a_static_scene():
    module = SmokeFireModule("cam", {"warmup_frames": 3, "sustain_seconds": 0.1})
    assert feed(module, blank(), times=20) is None


# ----------------------------------------------------------------- movement
def test_running_needs_a_fast_move():
    # 100px of a 320px-wide frame: above the 10% threshold, below the 35% the
    # tracker will still accept as one person.
    module = RunningModule("cam", {"speed_threshold": 0.1, "min_frames": 1})
    feed(module, blank(), [(10, 100, 40, 40)])
    alert = feed(module, blank(), [(110, 100, 40, 40)])
    assert alert is not None and alert.detail["speed_percent_of_frame"] > 10


def test_running_ignores_a_walk():
    module = RunningModule("cam", {"speed_threshold": 0.3, "min_frames": 1})
    feed(module, blank(), [(100, 100, 40, 40)])
    assert feed(module, blank(), [(112, 100, 40, 40)]) is None


def test_running_ignores_a_jump_too_big_to_be_one_person():
    # Beyond max_step the two boxes are not paired at all: reporting this as a
    # sprint is how a busy corridor would produce constant false alarms.
    module = RunningModule("cam", {"speed_threshold": 0.1, "min_frames": 1, "max_step": 0.35})
    feed(module, blank(), [(10, 100, 40, 40)])
    assert feed(module, blank(), [(300, 100, 40, 40)]) is None


def test_line_cross_reports_a_crossing():
    module = LineCrossModule("cam", {"line": [[0.0, 0.5], [1.0, 0.5]], "cooldown_seconds": 0})
    feed(module, blank(), [(100, 20, 40, 40)])  # above the line
    alert = feed(module, blank(), [(100, 190, 40, 40)])  # now below it
    assert alert is not None
    assert alert.detail["forward_total"] + alert.detail["backward_total"] == 1


def test_line_cross_quiet_without_a_crossing():
    module = LineCrossModule("cam", {"line": [[0.0, 0.5], [1.0, 0.5]]})
    feed(module, blank(), [(100, 20, 40, 40)])
    assert feed(module, blank(), [(120, 30, 40, 40)]) is None


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
