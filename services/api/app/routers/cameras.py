import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Camera, User, UserRole
from ..schemas import CameraCreate, CameraOut, CameraStreamConfig, CameraUpdate
from ..security import decrypt_secret, encrypt_secret, get_current_user, require_roles, require_service_key
from ..services.audit import log_action

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("", response_model=list[CameraOut])
def list_cameras(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Camera]:
    return list(db.scalars(select(Camera).order_by(Camera.name)).all())


@router.post("", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
def create_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.admin)),
) -> Camera:
    data = payload.model_dump(exclude={"password"})
    camera = Camera(**data, password_enc=encrypt_secret(payload.password))
    db.add(camera)
    db.commit()
    db.refresh(camera)
    log_action(db, actor, "camera.create", entity="camera", entity_id=str(camera.id), detail={"name": camera.name})
    return camera


@router.patch("/{camera_id}", response_model=CameraOut)
def update_camera(
    camera_id: uuid.UUID,
    payload: CameraUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.admin)),
) -> Camera:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")

    updates = payload.model_dump(exclude_unset=True)
    if "password" in updates:
        camera.password_enc = encrypt_secret(updates.pop("password"))
    for field, value in updates.items():
        setattr(camera, field, value)

    db.commit()
    db.refresh(camera)
    log_action(db, actor, "camera.update", entity="camera", entity_id=str(camera_id), detail={"name": camera.name})
    return camera


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(
    camera_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.admin)),
) -> None:
    camera = db.get(Camera, camera_id)
    if camera is not None:
        log_action(db, actor, "camera.delete", entity="camera", entity_id=str(camera_id), detail={"name": camera.name})
        db.delete(camera)
        db.commit()


# ------------------------------------------------- face-service endpoints
@router.get(
    "/stream-config",
    response_model=list[CameraStreamConfig],
    dependencies=[Depends(require_service_key)],
)
def stream_config(db: Session = Depends(get_db)) -> list[CameraStreamConfig]:
    """Enabled cameras with decrypted credentials, for the capture workers."""
    cameras = db.scalars(select(Camera).where(Camera.enabled.is_(True))).all()
    return [
        CameraStreamConfig(
            **CameraOut.model_validate(camera).model_dump(),
            password=decrypt_secret(camera.password_enc),
        )
        for camera in cameras
    ]


@router.post(
    "/{camera_id}/heartbeat",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_service_key)],
)
async def heartbeat(camera_id: uuid.UUID, online: bool = True, db: Session = Depends(get_db)) -> None:
    """Capture worker reports whether the stream is alive."""
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")

    camera.online = online
    camera.last_seen_at = datetime.now().astimezone()
    db.commit()

    from ..ws import manager

    await manager.broadcast(
        "camera-status",
        {"camera_id": str(camera.id), "online": online, "last_seen_at": camera.last_seen_at.isoformat()},
    )
