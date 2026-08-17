import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Event, Person, PersonRole, User, UserRole
from ..schemas import (
    EventOut,
    GuestRow,
    PersonDetail,
    PersonMergeRequest,
    PersonOut,
    PersonUpdate,
    StayOut,
)
from ..security import get_current_user, require_roles
from ..services import audit, occupancy, recognition, stays

router = APIRouter(prefix="/api/persons", tags=["persons"])


@router.get("", response_model=list[PersonOut])
def list_persons(
    q: str | None = Query(default=None, description="Search by name or room number"),
    role: PersonRole | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Person]:
    stmt = select(Person).where(Person.deleted_at.is_(None), Person.merged_into.is_(None))
    if role is not None:
        stmt = stmt.where(Person.role == role)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(Person.display_name.ilike(pattern) | Person.room_number.ilike(pattern))

    return list(db.scalars(stmt.order_by(Person.last_seen_at.desc()).offset(offset).limit(limit)).all())


@router.get("/present", response_model=list[GuestRow])
def list_present(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[GuestRow]:
    """Everyone currently inside the hotel, with their running night count."""
    inside_ids = {row[0] for row in occupancy.people_inside(db)}
    if not inside_ids:
        return []

    people = db.scalars(select(Person).where(Person.id.in_(inside_ids))).all()
    rows: list[GuestRow] = []

    for person in people:
        stay = stays.get_active_stay(db, person.id)
        rows.append(
            GuestRow(
                person_id=person.id,
                display_name=person.display_name,
                role=person.role,
                room_number=person.room_number,
                reference_image=person.reference_image,
                first_entry=stay.checkin_at if stay else person.first_seen_at,
                last_exit=None,
                nights=stays.count_nights(stay.checkin_at, None) if stay else 0,
                present=True,
            )
        )

    return sorted(rows, key=lambda r: r.first_entry, reverse=True)


@router.get("/{person_id}", response_model=PersonDetail)
def get_person(
    person_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PersonDetail:
    person = db.get(Person, person_id)
    if person is None or person.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")

    active = stays.get_active_stay(db, person.id)
    inside = person.id in {row[0] for row in occupancy.people_inside(db)}

    detail = PersonDetail.model_validate(person)
    detail.total_nights = stays.total_nights(db, person.id)
    detail.present = inside
    detail.current_stay_nights = stays.count_nights(active.checkin_at, None) if active else 0
    return detail


@router.patch("/{person_id}", response_model=PersonOut)
def update_person(
    person_id: uuid.UUID,
    payload: PersonUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.admin, UserRole.manager, UserRole.reception)),
) -> Person:
    person = db.get(Person, person_id)
    if person is None or person.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(person, field, value)

    db.commit()
    db.refresh(person)
    audit.log_action(db, actor, "person.update", entity="person", entity_id=str(person_id), detail=changes)
    return person


@router.get("/{person_id}/events", response_model=list[EventOut])
def person_events(
    person_id: uuid.UUID,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Event]:
    return list(
        db.scalars(
            select(Event)
            .where(Event.person_id == person_id)
            .order_by(Event.occurred_at.desc())
            .limit(limit)
        ).all()
    )


@router.get("/{person_id}/stays", response_model=list[StayOut])
def person_stays(
    person_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[stays.Stay]:
    return list(
        db.scalars(
            select(stays.Stay)
            .where(stays.Stay.person_id == person_id)
            .order_by(stays.Stay.checkin_at.desc())
        ).all()
    )


@router.post("/merge", response_model=PersonOut)
def merge(
    payload: PersonMergeRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
) -> Person:
    """Fix a false split — two IDs that are really the same person."""
    try:
        result = recognition.merge_persons(db, payload.source_id, payload.target_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    audit.log_action(
        db, actor, "person.merge", entity="person", entity_id=str(payload.source_id),
        detail={"target_id": str(payload.target_id)},
    )
    return result


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def forget(
    person_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.admin)),
) -> None:
    """Right to be forgotten — erases biometrics and imagery for this person."""
    recognition.forget_person(db, person_id)
    audit.log_action(db, actor, "person.forget", entity="person", entity_id=str(person_id))
