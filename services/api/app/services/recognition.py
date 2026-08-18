"""Face matching, identity assignment and in/out event recording."""

import base64
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    Camera,
    CameraPurpose,
    Event,
    EventDirection,
    FaceEmbedding,
    Person,
    PersonRole,
)
from ..schemas import RecognizeRequest, RecognizeResponse
from . import stays
from .storage import save_face_image
from .vector_search import find_match

log = logging.getLogger(__name__)

# A second embedding is only stored for a person when the new face is a clear
# but not identical match — that is what broadens pose/lighting coverage.
ENROLL_LOWER = 0.50
ENROLL_UPPER = 0.85
MAX_EMBEDDINGS_PER_PERSON = 15


def resolve_direction(db: Session, person_id: uuid.UUID, camera: Camera | None,
                      hint: EventDirection | None) -> EventDirection:
    """Decide whether this sighting is an entry or an exit.

    Priority: explicit hint from the edge (line-crossing) > dedicated
    entry/exit camera > alternate from the person's previous event.
    """
    if hint is not None:
        return hint
    if camera is not None:
        if camera.purpose is CameraPurpose.entry:
            return EventDirection.in_
        if camera.purpose is CameraPurpose.exit:
            return EventDirection.out

    last = db.scalar(
        select(Event).where(Event.person_id == person_id).order_by(Event.occurred_at.desc()).limit(1)
    )
    if last is None:
        return EventDirection.in_
    return EventDirection.out if last.direction is EventDirection.in_ else EventDirection.in_


def is_debounced(db: Session, person_id: uuid.UUID, at: datetime) -> bool:
    """True when the same person was already logged moments ago.

    Without this, a person lingering in frame produces an event per sampled
    frame and the occupancy counter oscillates.
    """
    window = at - timedelta(seconds=settings.event_debounce_seconds)
    recent = db.scalar(
        select(Event)
        .where(Event.person_id == person_id, Event.occurred_at >= window)
        .order_by(Event.occurred_at.desc())
        .limit(1)
    )
    return recent is not None


def process_detection(db: Session, payload: RecognizeRequest) -> RecognizeResponse:
    at = payload.detected_at or datetime.now().astimezone()
    camera = db.get(Camera, payload.camera_id) if payload.camera_id else None

    person, similarity = find_match(db, payload.embedding)
    is_new = person is None

    image_path: str | None = None
    if payload.image_base64:
        image_path = save_face_image(base64.b64decode(payload.image_base64), at)

    if is_new:
        person = Person(
            role=PersonRole.unknown,
            reference_image=image_path,
            first_seen_at=at,
            last_seen_at=at,
        )
        db.add(person)
        db.flush()
        db.add(
            FaceEmbedding(
                person_id=person.id,
                embedding=payload.embedding,
                image_path=image_path,
                quality=payload.quality,
            )
        )
    else:
        person.last_seen_at = at
        _maybe_enroll(db, person, payload, similarity, image_path)

    if is_debounced(db, person.id, at):
        db.commit()
        return RecognizeResponse(
            person_id=person.id,
            is_new_person=is_new,
            similarity=similarity,
            event_id=None,
            direction=None,
            debounced=True,
        )

    direction = resolve_direction(db, person.id, camera, payload.direction_hint)
    event = Event(
        person_id=person.id,
        camera_id=camera.id if camera else None,
        direction=direction,
        occurred_at=at,
        confidence=payload.confidence,
        image_path=image_path,
    )
    db.add(event)

    if direction is EventDirection.in_:
        stays.open_stay(db, person.id, at, person.room_number)
    else:
        stays.touch_stay(db, person.id, at)

    db.commit()
    db.refresh(event)

    return RecognizeResponse(
        person_id=person.id,
        is_new_person=is_new,
        similarity=similarity,
        event_id=event.id,
        direction=direction,
        debounced=False,
    )


def _maybe_enroll(db: Session, person: Person, payload: RecognizeRequest,
                  similarity: float | None, image_path: str | None) -> None:
    """Add an extra reference vector when it adds genuinely new information."""
    if similarity is None or not (ENROLL_LOWER <= similarity <= ENROLL_UPPER):
        return
    existing = db.scalar(
        select(func.count(FaceEmbedding.id)).where(FaceEmbedding.person_id == person.id)
    )
    if existing >= MAX_EMBEDDINGS_PER_PERSON:
        return
    db.add(
        FaceEmbedding(
            person_id=person.id,
            embedding=payload.embedding,
            image_path=image_path,
            quality=payload.quality,
        )
    )


def merge_persons(db: Session, source_id: uuid.UUID, target_id: uuid.UUID) -> Person:
    """Fold a duplicate identity into the correct one, keeping all history."""
    if source_id == target_id:
        raise ValueError("Cannot merge a person into itself")

    source = db.get(Person, source_id)
    target = db.get(Person, target_id)
    if source is None or target is None:
        raise ValueError("Person not found")

    for table in (FaceEmbedding, Event):
        for row in db.scalars(select(table).where(table.person_id == source_id)).all():
            row.person_id = target_id

    _merge_stays(db, source_id, target_id)

    target.first_seen_at = min(target.first_seen_at, source.first_seen_at)
    target.last_seen_at = max(target.last_seen_at, source.last_seen_at)
    target.display_name = target.display_name or source.display_name
    target.room_number = target.room_number or source.room_number
    target.phone = target.phone or source.phone

    source.merged_into = target_id
    source.deleted_at = datetime.now().astimezone()

    db.commit()
    db.refresh(target)
    return target


def _merge_stays(db: Session, source_id: uuid.UUID, target_id: uuid.UUID) -> None:
    """Move the source's stays onto the target, keeping exactly one active.

    Both identities can have an open stay — they were, after all, the same
    person walking around. Only one may survive as active (the DB enforces
    it), so the two collapse into the earlier check-in.
    """
    source_stays = db.scalars(select(stays.Stay).where(stays.Stay.person_id == source_id)).all()
    target_active = stays.get_active_stay(db, target_id)

    for stay in source_stays:
        if not stay.active:
            stay.person_id = target_id
            continue

        if target_active is None:
            stay.person_id = target_id
            target_active = stay
            continue

        # Two open stays for one person: keep the earlier start, drop the copy.
        target_active.checkin_at = min(target_active.checkin_at, stay.checkin_at)
        target_active.room_number = target_active.room_number or stay.room_number
        target_active.nights = stays.count_nights(target_active.checkin_at, None)
        db.delete(stay)

    db.flush()


def forget_person(db: Session, person_id: uuid.UUID) -> None:
    """Right-to-be-forgotten: erase biometrics and imagery, keep no identity."""
    person = db.get(Person, person_id)
    if person is None:
        return

    for face in db.scalars(select(FaceEmbedding).where(FaceEmbedding.person_id == person_id)).all():
        _unlink(face.image_path)
        db.delete(face)

    for event in db.scalars(select(Event).where(Event.person_id == person_id)).all():
        _unlink(event.image_path)
        event.image_path = None

    _unlink(person.reference_image)
    person.reference_image = None
    person.display_name = None
    person.phone = None
    person.deleted_at = datetime.now().astimezone()
    db.commit()


def _unlink(relative_path: str | None) -> None:
    if not relative_path:
        return
    try:
        Path(settings.media_root, relative_path).unlink(missing_ok=True)
    except OSError:
        log.warning("Could not remove media file %s", relative_path)
