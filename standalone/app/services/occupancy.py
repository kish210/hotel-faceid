"""Live occupancy and time-series analytics (SQLite-compatible).

PostgreSQL's `date_trunc` and `FILTER (WHERE …)` aggregates don't exist on
SQLite, so time bucketing happens in Python over the raw event rows.
"""

from datetime import datetime, time, timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from ..models import Camera, Event, EventDirection, Person, PersonRole, Stay
from ..schemas import DailyReportRow, DashboardOut, HourBucket, OccupancyOut, TopGuestRow
from .stays import TZ



def _latest_event_per_person(as_of: datetime | None = None) -> Select:
    """One row per person: their most recent event at or before `as_of`.

    Occupancy is derived from each person's last known direction rather than
    sum(in) - sum(out), so a single missed detection cannot permanently skew
    the counter.
    """
    stmt = select(
        Event.person_id,
        Event.direction,
        func.row_number()
        .over(partition_by=Event.person_id, order_by=Event.occurred_at.desc())
        .label("rn"),
    )
    if as_of is not None:
        stmt = stmt.where(Event.occurred_at <= as_of)
    return stmt.subquery()


def people_inside(db: Session, as_of: datetime | None = None) -> list[tuple]:
    latest = _latest_event_per_person(as_of)
    return db.execute(
        select(Person.id, Person.role)
        .join(latest, latest.c.person_id == Person.id)
        .where(latest.c.rn == 1, latest.c.direction == EventDirection.in_, Person.deleted_at.is_(None))
    ).all()


def current_occupancy(db: Session, as_of: datetime | None = None) -> OccupancyOut:
    rows = people_inside(db, as_of)
    counts = {role: 0 for role in PersonRole}
    for _, role in rows:
        counts[role] += 1

    return OccupancyOut(
        total=len(rows),
        guests=counts[PersonRole.guest] + counts[PersonRole.unknown],
        staff=counts[PersonRole.staff],
        visitors=counts[PersonRole.visitor],
        as_of=as_of or datetime.now(TZ),
    )


def _direction_counts(
    db: Session, predicate=None
) -> tuple[int, int]:
    """(entries, exits) counted from raw rows — no FILTER() needed."""
    stmt = select(Event.direction)
    if predicate is not None:
        stmt = stmt.where(predicate)
    rows = db.execute(stmt).all()

    entries = exits = 0
    for (direction,) in rows:
        if direction is EventDirection.in_:
            entries += 1
        elif direction is EventDirection.out:
            exits += 1
    return entries, exits


def hourly_flow(db: Session, hours: int = 24) -> list[HourBucket]:
    since = datetime.now(TZ) - timedelta(hours=hours)
    rows = db.execute(
        select(Event.occurred_at, Event.direction).where(Event.occurred_at >= since)
    ).all()

    entries: dict[datetime, int] = {}
    exits: dict[datetime, int] = {}
    for occurred_at, direction in rows:
        hour = occurred_at.astimezone(TZ).replace(minute=0, second=0, microsecond=0)
        target = entries if direction is EventDirection.in_ else exits
        target[hour] = target.get(hour, 0) + 1

    hours_seen = sorted(set(entries) | set(exits))
    return [
        HourBucket(hour=h, entries=entries.get(h, 0), exits=exits.get(h, 0)) for h in hours_seen
    ]


def dashboard(db: Session) -> DashboardOut:
    start_of_day = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)

    today_entries, today_exits = _direction_counts(db, Event.occurred_at >= start_of_day)

    active_stays = db.scalar(select(func.count(Stay.id)).where(Stay.active.is_(True))) or 0
    cameras_total = db.scalar(select(func.count(Camera.id))) or 0
    cameras_online = db.scalar(select(func.count(Camera.id)).where(Camera.online.is_(True))) or 0

    return DashboardOut(
        occupancy=current_occupancy(db),
        today_entries=today_entries,
        today_exits=today_exits,
        active_stays=active_stays,
        cameras_online=cameras_online,
        cameras_total=cameras_total,
        last_24h=hourly_flow(db),
    )


def daily_report(db: Session, start: datetime, end: datetime) -> list[DailyReportRow]:
    rows = db.execute(
        select(Event.person_id, Event.direction, Event.occurred_at).where(
            Event.occurred_at >= start, Event.occurred_at < end
        )
    ).all()

    by_day: dict = {}
    for person_id, direction, occurred_at in rows:
        day = occurred_at.astimezone(TZ).date()
        bucket = by_day.setdefault(day, {"entries": 0, "exits": 0, "people": set()})
        if direction is EventDirection.in_:
            bucket["entries"] += 1
        elif direction is EventDirection.out:
            bucket["exits"] += 1
        bucket["people"].add(person_id)

    report: list[DailyReportRow] = []
    for day in sorted(by_day):
        bucket = by_day[day]
        samples = [
            current_occupancy(db, datetime.combine(day, time(hour=hour), tzinfo=TZ)).total
            for hour in range(0, 24, 4)
]
        report.append(
            DailyReportRow(
                day=datetime.combine(day, time(hour=0), tzinfo=TZ),
                entries=bucket["entries"],
                exits=bucket["exits"],
                unique_people=len(bucket["people"]),
                avg_occupancy=round(sum(samples) / len(samples), 2),
            )
        )
    return report


def top_guests(db: Session, limit: int = 20) -> list[TopGuestRow]:
    rows = db.execute(
        select(
            Person.id,
            Person.display_name,
            Person.reference_image,
            func.coalesce(func.sum(Stay.nights), 0).label("total_nights"),
            func.count(Stay.id).label("visits"),
        )
        .join(Stay, Stay.person_id == Person.id)
        .where(Person.deleted_at.is_(None))
        .group_by(Person.id, Person.display_name, Person.reference_image)
        .order_by(func.coalesce(func.sum(Stay.nights), 0).desc())
        .limit(limit)
    ).all()

    return [
        TopGuestRow(
            person_id=r.id,
            display_name=r.display_name,
            reference_image=r.reference_image,
            total_nights=int(r.total_nights),
            visits=r.visits,
        )
        for r in rows
    ]
