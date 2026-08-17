import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Event, EventDirection, User, UserRole
from ..schemas import EventCreate, EventOut, RecognizeRequest, RecognizeResponse
from ..security import get_current_user, require_roles, require_service_key
from ..services import occupancy, recognition, stays
from ..ws import manager

router = APIRouter(prefix="/api", tags=["events"])


@router.post(
    "/recognize",
    response_model=RecognizeResponse,
    dependencies=[Depends(require_service_key)],
)
async def recognize(payload: RecognizeRequest, db: Session = Depends(get_db)) -> RecognizeResponse:
    """Ingest one face detection from the face-service.

    Runs the blocking DB work in a thread so a burst of detections cannot
    stall the event loop that serves the dashboard's WebSockets.
    """
    result = await asyncio.to_thread(recognition.process_detection, db, payload)

    if not result.debounced:
        await manager.broadcast(
            "event",
            {
                "person_id": str(result.person_id),
                "direction": result.direction.value if result.direction else None,
                "is_new_person": result.is_new_person,
                "similarity": result.similarity,
            },
        )
        await manager.broadcast(
            "occupancy",
            (await asyncio.to_thread(occupancy.current_occupancy, db)).model_dump(),
        )

    return result


@router.get("/events", response_model=list[EventOut])
def list_events(
    direction: EventDirection | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Event]:
    stmt = select(Event)
    if direction is not None:
        stmt = stmt.where(Event.direction == direction)
    if since is not None:
        stmt = stmt.where(Event.occurred_at >= since)
    if until is not None:
        stmt = stmt.where(Event.occurred_at <= until)

    return list(
        db.scalars(stmt.order_by(Event.occurred_at.desc()).offset(offset).limit(limit)).all()
    )


@router.post("/events", response_model=EventOut)
async def create_manual_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.manager, UserRole.reception, UserRole.security)),
) -> Event:
    """Operator correction for a missed or misdirected passage."""
    at = payload.occurred_at or datetime.now().astimezone()
    event = Event(
        person_id=payload.person_id,
        camera_id=payload.camera_id,
        direction=payload.direction,
        occurred_at=at,
        manual=True,
    )
    db.add(event)

    if payload.direction is EventDirection.in_:
        stays.open_stay(db, payload.person_id, at)
    else:
        stays.touch_stay(db, payload.person_id, at)

    db.commit()
    db.refresh(event)

    await manager.broadcast("occupancy", occupancy.current_occupancy(db).model_dump())
    return event
