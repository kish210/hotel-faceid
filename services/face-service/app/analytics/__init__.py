"""Analytics modules: what the system watches for besides faces.

`build_pipeline` turns the module ids stored on a camera into live instances.
Ids the build does not know — an older service meeting a newer panel — are
skipped with a warning rather than stopping the camera.
"""

from __future__ import annotations

import logging

from .anpr import AnprModule, is_available as anpr_available
from .base import Alert, AnalyticsModule, FrameContext
from .fire import SmokeFireModule
from .motion import (
    CrowdModule,
    FightModule,
    IntrusionModule,
    LoiteringModule,
    ObjectLeftModule,
)
from .movement import LineCrossModule, RunningModule
from .scene import BlackoutModule, DefocusModule, TamperModule

log = logging.getLogger(__name__)

MODULES: dict[str, type[AnalyticsModule]] = {
    # people and behaviour
    IntrusionModule.id: IntrusionModule,
    FightModule.id: FightModule,
    CrowdModule.id: CrowdModule,
    LoiteringModule.id: LoiteringModule,
    RunningModule.id: RunningModule,
    LineCrossModule.id: LineCrossModule,
    ObjectLeftModule.id: ObjectLeftModule,
    # safety
    SmokeFireModule.id: SmokeFireModule,
    # the camera's own health
    TamperModule.id: TamperModule,
    DefocusModule.id: DefocusModule,
    BlackoutModule.id: BlackoutModule,
    # pack-backed
    AnprModule.id: AnprModule,
}

#: modules that need a downloaded pack before they can run
AVAILABILITY = {AnprModule.id: anpr_available}


def build_pipeline(
    camera_name: str, module_ids: list[str] | None, config: dict | None
) -> list[AnalyticsModule]:
    config = config or {}
    pipeline: list[AnalyticsModule] = []

    for module_id in module_ids or []:
        factory = MODULES.get(module_id)
        if factory is None:
            log.warning("Unknown analytics module %r on %s — skipped", module_id, camera_name)
            continue

        check = AVAILABILITY.get(module_id)
        if check is not None and not check():
            log.warning(
                "Module %r is enabled on %s but its model pack is not installed",
                module_id,
                camera_name,
            )
            continue

        pipeline.append(factory(camera_name, config.get(module_id)))

    return pipeline


__all__ = ["Alert", "AnalyticsModule", "FrameContext", "MODULES", "build_pipeline"]
