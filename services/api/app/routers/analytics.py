from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Camera, User, UserRole
from ..schemas import AnalyticsModuleOut, ModuleInstallRequest
from ..security import get_current_user, require_roles
from ..services import analytics_modules
from ..services.audit import log_action

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _usage(db: Session) -> dict[str, int]:
    """How many cameras each module is switched on for."""
    counts: dict[str, int] = {}
    for (enabled,) in db.execute(select(Camera.analytics)):
        for module_id in enabled or []:
            counts[module_id] = counts.get(module_id, 0) + 1
    return counts


def _to_out(spec, counts: dict[str, int]) -> AnalyticsModuleOut:
    return AnalyticsModuleOut(
        id=spec.id,
        name=spec.name,
        description=spec.description,
        version=spec.version,
        installed=analytics_modules.is_installed(spec),
        needs_pack=spec.pack_entry is not None,
        pack_size_mb=spec.pack_size_mb,
        cpu_cost=spec.cpu_cost,
        cameras=counts.get(spec.id, 0),
        settings=spec.settings,
    )


@router.post("/modules/refresh", response_model=list[AnalyticsModuleOut])
def refresh_modules(
    payload: ModuleInstallRequest | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.admin)),
) -> list[AnalyticsModuleOut]:
    """Pull the module list from the repository.

    This is what makes a module added after this build was installed appear in
    the panel: the catalogue is data, not code.
    """
    try:
        count = analytics_modules.refresh_catalogue(payload.source_url if payload else None)
    except analytics_modules.ModuleError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    log_action(db, actor, "module.refresh", entity="module", detail={"modules": count})
    counts = _usage(db)
    return [_to_out(spec, counts) for spec in analytics_modules.CATALOGUE]


@router.get("/modules", response_model=list[AnalyticsModuleOut])
def list_modules(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AnalyticsModuleOut]:
    """Everything the system can watch for, and whether it is ready to use."""
    counts = _usage(db)
    return [_to_out(spec, counts) for spec in analytics_modules.CATALOGUE]


@router.post("/modules/{module_id}/install", response_model=AnalyticsModuleOut)
def install_module(
    module_id: str,
    payload: ModuleInstallRequest | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.admin)),
) -> AnalyticsModuleOut:
    """Download and unpack a module's model files.

    Installing an already-installed module reinstalls it, which is how an
    operator applies a newer pack.
    """
    spec = analytics_modules.BY_ID.get(module_id)
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found")

    try:
        analytics_modules.install(spec, payload.source_url if payload else None)
    except analytics_modules.ModuleError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    log_action(db, actor, "module.install", entity="module", entity_id=module_id)
    return _to_out(spec, _usage(db))


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_module(
    module_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.admin)),
) -> None:
    """Delete a module's downloaded files, freeing the disk space.

    Cameras keep the module in their list: reinstalling brings it straight
    back rather than making the operator reconfigure every camera.
    """
    spec = analytics_modules.BY_ID.get(module_id)
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found")

    analytics_modules.remove(spec)
    log_action(db, actor, "module.remove", entity="module", entity_id=module_id)
