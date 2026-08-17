import socket
import time
import uuid
from datetime import datetime

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from requests.auth import HTTPDigestAuth
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


# --------------------------------------------------- live view + diagnostics
SNAPSHOT_PATHS = {
    "dahua": "/cgi-bin/snapshot.cgi?channel=1&noreq=0",
    "hikvision": "/ISAPI/Streaming/channels/101/picture",
}


def _camera_http(camera: Camera) -> tuple[str, tuple[str, str] | None]:
    """Return (base_url, digest_auth) for a camera, or (base_url, None)."""
    base = f"http://{camera.host}:{camera.port}"
    password = decrypt_secret(camera.password_enc)
    if camera.username:
        return base, (camera.username, password or "")
    return base, None


def _camera_snapshot(camera: Camera) -> bytes | None:
    """Fetch a fresh JPEG from the camera's HTTP snapshot endpoint."""
    path = SNAPSHOT_PATHS.get(camera.brand)
    if not path:
        return None
    base, auth = _camera_http(camera)
    try:
        if auth:
            response = requests.get(base + path, auth=HTTPDigestAuth(*auth), timeout=8)
        else:
            response = requests.get(base + path, timeout=8)
        response.raise_for_status()
        body = response.content or b""
        return body if body[:2] == b"\xff\xd8" else None
    except requests.RequestException:
        return None


@router.get("/{camera_id}/snapshot")
def camera_snapshot(
    camera_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    """Live JPEG frame proxied through the server (browsers can't reach the LAN)."""
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")

    image = _camera_snapshot(camera)
    if image is None:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "دوربین در دسترس نیست یا snapshot پشتیبانی نمی‌شود",
        )
    return Response(
        content=image,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@router.post("/{camera_id}/check-connection")
async def check_connection(
    camera_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Probe the camera (TCP + snapshot) and refresh its live status."""
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")

    def tcp_ok(port: int) -> bool:
        try:
            with socket.create_connection((camera.host, port), timeout=5):
                return True
        except OSError:
            return False

    started = time.monotonic()
    http_reachable = tcp_ok(camera.port)
    rtsp_reachable = tcp_ok(554)
    latency_ms = int((time.monotonic() - started) * 1000)

    snapshot_ok = False
    if http_reachable:
        snapshot_ok = _camera_snapshot(camera) is not None

    online = http_reachable or rtsp_reachable
    camera.online = online
    camera.last_seen_at = datetime.now().astimezone()
    db.commit()

    from ..ws import manager

    await manager.broadcast(
        "camera-status",
        {"camera_id": str(camera.id), "online": online, "last_seen_at": camera.last_seen_at.isoformat()},
    )

    detail = (
        "✓ دوربین آنلاین؛ snapshot دریافت شد"
        if snapshot_ok
        else "دوربین قابل دسترسی است اما snapshot دریافت نشد (برند/مجوز را بررسی کنید)"
        if http_reachable
        else rtsp_reachable
        and "HTTP بسته است اما RTSP (554) باز است"
        or "دوربین قابل دسترسی نیست"
    )

    return {
        "online": online,
        "host": camera.host,
        "http_port": camera.port,
        "http_reachable": http_reachable,
        "rtsp_reachable": rtsp_reachable,
        "snapshot_ok": snapshot_ok,
        "latency_ms": latency_ms,
        "detail": detail,
    }


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
