"""Live occupancy and time-series analytics.

Grouping by calendar buckets is done in Python so the same logic runs on
SQLite and Postgres (date_trunc is Postgres-only).
"""

from datetime import datetime, timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from ..models import Camera, Event, EventDirection, Person, PersonGender, PersonRole, Stay
from ..schemas import DailyReportRow, DashboardOut, HourBucket, OccupancyOut, TopGuestRow
from .stays import TZ


def _latest_direction_per_person(db: Session, as_of: datetime | None = None) -> dict[int, EventDirection]:
    """Most recent event direction per person id, computed in Python."""
    stmt = select(Event.person_id, Event.direction, Event.occurred_at)
    if as_of is not None:
        stmt = stmt.where(Event.occurred_at <= as_of)
    latest: dict[int, EventDirection] = {}
    for person_id, direction, occurred_at in db.execute(stmt):
        if person_id not in latest or occurred_at > latest[person_id][1]:
            latest[person_id] = (direction, occurred_at)
    return {pid: tup[0] for pid, tup in latest.items()}


def people_inside(db: Session, as_of: datetime | None = None) -> list[tuple]:
    """Rows of (person_id, role, gender) for everyone currently inside."""
    latest = _latest_direction_per_person(db, as_of)
    if not latest:
        return []
    rows = db.execute(
        select(Person.id, Person.role, Person.gender).where(
            Person.id.in_(list(latest.keys())),
            Person.deleted_at.is_(None),
        )
    ).all()
    return [
        (pid, role, gender)
        for pid, role, gender in rows
        if latest[pid] is EventDirection.in_
    ]


def current_occupancy(db: Session, as_of: datetime | None = None) -> OccupancyOut:
    rows = people_inside(db, as_of)
    counts = {role: 0 for role in PersonRole}
    genders = {gender: 0 for gender in PersonGender}
    for _, role, gender in rows:
        counts[role] += 1
        genders[gender or PersonGender.unknown] += 1

    return OccupancyOut(
        total=len(rows),
        guests=counts[PersonRole.guest] + counts[PersonRole.unknown],
        staff=counts[PersonRole.staff],
        visitors=counts[PersonRole.visitor],
        males=genders[PersonGender.male],
        females=genders[PersonGender.female],
        unknown_gender=genders[PersonGender.unknown],
        as_of=as_of or datetime.now(TZ),
    )


def hourly_flow(db: Session, hours: int = 24) -> list[HourBucket]:
    since = datetime.now(TZ) - timedelta(hours=hours)
    rows = db.execute(
        select(Event.direction, Event.occurred_at).where(Event.occurred_at >= since)
    ).all()

    buckets: dict[datetime, HourBucket] = {}
    for direction, occurred_at in rows:
        bucket = occurred_at.replace(minute=0, second=0, microsecond=0)
        if bucket not in buckets:
            buckets[bucket] = HourBucket(hour=bucket, entries=0, exits=0)
        if direction is EventDirection.in_:
            buckets[bucket].entries += 1
        else:
            buckets[bucket].exits += 1

    return [buckets[k] for k in sorted(buckets)]


def dashboard(db: Session) -> DashboardOut:
    start_of_day = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)

    rows = db.execute(
        select(Event.direction).where(Event.occurred_at >= start_of_day)
    ).all()
    today_entries = sum(1 for (direction,) in rows if direction is EventDirection.in_)
    today_exits = len(rows) - today_entries

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
        select(Event.direction, Event.person_id, Event.occurred_at).where(
            Event.occurred_at >= start, Event.occurred_at < end
        )
    ).all()

    by_day: dict[datetime, dict] = {}
    for direction, person_id, occurred_at in rows:
        day = occurred_at.replace(hour=0, minute=0, second=0, microsecond=0)
        bucket = by_day.setdefault(day, {"entries": 0, "exits": 0, "people": set()})
        if direction is EventDirection.in_:
            bucket["entries"] += 1
        else:
            bucket["exits"] += 1
        bucket["people"].add(person_id)

    report: list[DailyReportRow] = []
    for day in sorted(by_day):
        bucket = by_day[day]
        # Sample occupancy every 4 hours to approximate the daily average.
        samples = [current_occupancy(db, day.replace(hour=h)).total for h in range(0, 24, 4)]
        report.append(
            DailyReportRow(
                day=day,
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
