import base64
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Alert, AlertSeverity, Camera, User, UserRole
from ..schemas import AlertCreate, AlertOut
from ..security import get_current_user, require_roles, require_service_key
from ..services import analytics_modules
from ..services.audit import log_action
from ..services.storage import save_face_image

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _to_out(alert: Alert, camera_names: dict) -> AlertOut:
    out = AlertOut.model_validate(alert)
    out.camera_name = camera_names.get(alert.camera_id)
    spec = analytics_modules.BY_ID.get(alert.module)
    out.module_name = spec.name if spec else alert.module
    return out


@router.get("", response_model=list[AlertOut])
def list_alerts(
    module: str | None = None,
    severity: AlertSeverity | None = None,
    unacknowledged: bool = Query(default=False, description="Only alerts nobody has seen yet"),
    since_hours: int = Query(default=168, le=24 * 90),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AlertOut]:
    stmt = select(Alert).where(
        Alert.occurred_at >= datetime.now().astimezone() - timedelta(hours=since_hours)
    )
    if module:
        stmt = stmt.where(Alert.module == module)
    if severity is not None:
        stmt = stmt.where(Alert.severity == severity)
    if unacknowledged:
        stmt = stmt.where(Alert.acknowledged_at.is_(None))

    alerts = list(db.scalars(stmt.order_by(Alert.occurred_at.desc()).limit(limit)).all())
    names = {camera.id: camera.name for camera in db.scalars(select(Camera)).all()}
    return [_to_out(alert, names) for alert in alerts]


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge(
    alert_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> AlertOut:
    """Mark an alert as seen, so the operator's queue empties as they work."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")

    alert.acknowledged_at = datetime.now().astimezone()
    alert.acknowledged_by = actor.id
    db.commit()
    db.refresh(alert)

    names = {camera.id: camera.name for camera in db.scalars(select(Camera)).all()}
    return _to_out(alert, names)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
) -> None:
    alert = db.get(Alert, alert_id)
    if alert is not None:
        log_action(db, actor, "alert.delete", entity="alert", entity_id=str(alert_id))
        db.delete(alert)
        db.commit()


@router.post(
    "",
    response_model=AlertOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_service_key)],
)
async def create_alert(payload: AlertCreate, db: Session = Depends(get_db)) -> AlertOut:
    """Raised by an analytics module in the face-service."""
    occurred_at = payload.occurred_at or datetime.now().astimezone()

    image_path = None
    if payload.image_base64:
        image_path = save_face_image(base64.b64decode(payload.image_base64), occurred_at)

    alert = Alert(
        camera_id=payload.camera_id,
        module=payload.module,
        severity=payload.severity,
        title=payload.title,
        detail=payload.detail,
        image_path=image_path,
        person_id=payload.person_id,
        occurred_at=occurred_at,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    names = {camera.id: camera.name for camera in db.scalars(select(Camera)).all()}
    out = _to_out(alert, names)

    # Operators watching the panel should see it without refreshing.
    from ..ws import manager

    await manager.broadcast("alert", out.model_dump(mode="json"))
    return out
