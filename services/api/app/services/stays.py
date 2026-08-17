"""Stay bookkeeping: check-in, check-out and night counting."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Event, EventDirection, Stay

TZ = ZoneInfo(settings.hotel_timezone)


def count_nights(checkin: datetime, checkout: datetime | None) -> int:
    """Number of hotel midnights between check-in and check-out.

    A guest who arrives at 22:00 and leaves at 09:00 the next day crossed one
    midnight and is charged one night — so we count date boundaries in the
    hotel's local timezone, not elapsed 24h periods.
    """
    end = checkout or datetime.now(TZ)
    start_day = checkin.astimezone(TZ).date()
    end_day = end.astimezone(TZ).date()
    return max((end_day - start_day).days, 0)


def get_active_stay(db: Session, person_id) -> Stay | None:
    return db.scalar(select(Stay).where(Stay.person_id == person_id, Stay.active.is_(True)))


def open_stay(db: Session, person_id, at: datetime, room_number: str | None = None) -> Stay:
    """Return the person's active stay, creating one if they have none."""
    stay = get_active_stay(db, person_id)
    if stay is not None:
        return stay

    stay = Stay(person_id=person_id, checkin_at=at, room_number=room_number, active=True, nights=0)
    db.add(stay)
    db.flush()
    return stay


def touch_stay(db: Session, person_id, at: datetime) -> Stay | None:
    """Refresh the running night count on the person's active stay."""
    stay = get_active_stay(db, person_id)
    if stay is None:
        return None
    stay.nights = count_nights(stay.checkin_at, at)
    return stay


def close_stay(db: Session, stay: Stay, at: datetime) -> Stay:
    stay.checkout_at = at
    stay.nights = count_nights(stay.checkin_at, at)
    stay.active = False
    return stay


def close_stale_stays(db: Session) -> int:
    """Close stays whose guest has been outside longer than the timeout.

    Runs periodically. A guest who steps out for dinner keeps their stay open;
    one who has not been seen inside for STAY_TIMEOUT_HOURS is checked out at
    the time of their last exit.
    """
    cutoff = datetime.now(TZ) - timedelta(hours=settings.stay_timeout_hours)
    closed = 0

    for stay in db.scalars(select(Stay).where(Stay.active.is_(True))).all():
        last_event = db.scalar(
            select(Event)
            .where(Event.person_id == stay.person_id)
            .order_by(Event.occurred_at.desc())
            .limit(1)
        )
        if last_event is None:
            continue
        if last_event.direction is EventDirection.out and last_event.occurred_at < cutoff:
            close_stay(db, stay, last_event.occurred_at)
            closed += 1

    if closed:
        db.commit()
    return closed


def total_nights(db: Session, person_id) -> int:
    """Lifetime nights across every visit, including the one in progress."""
    stays = db.scalars(select(Stay).where(Stay.person_id == person_id)).all()
    return sum(s.nights if not s.active else count_nights(s.checkin_at, None) for s in stays)
