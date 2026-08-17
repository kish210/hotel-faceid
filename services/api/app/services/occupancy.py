"""Live occupancy and time-series analytics."""

from datetime import datetime, timedelta

from sqlalchemy import Select, distinct, func, select
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


def hourly_flow(db: Session, hours: int = 24) -> list[HourBucket]:
    since = datetime.now(TZ) - timedelta(hours=hours)
    bucket = func.date_trunc("hour", Event.occurred_at).label("hour")

    rows = db.execute(
        select(
            bucket,
            func.count().filter(Event.direction == EventDirection.in_).label("entries"),
            func.count().filter(Event.direction == EventDirection.out).label("exits"),
        )
        .where(Event.occurred_at >= since)
        .group_by(bucket)
        .order_by(bucket)
    ).all()

    return [HourBucket(hour=r.hour, entries=r.entries, exits=r.exits) for r in rows]


def dashboard(db: Session) -> DashboardOut:
    start_of_day = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)

    today = db.execute(
        select(
            func.count().filter(Event.direction == EventDirection.in_),
            func.count().filter(Event.direction == EventDirection.out),
        ).where(Event.occurred_at >= start_of_day)
    ).one()

    active_stays = db.scalar(select(func.count(Stay.id)).where(Stay.active.is_(True))) or 0
    cameras_total = db.scalar(select(func.count(Camera.id))) or 0
    cameras_online = db.scalar(select(func.count(Camera.id)).where(Camera.online.is_(True))) or 0

    return DashboardOut(
        occupancy=current_occupancy(db),
        today_entries=today[0],
        today_exits=today[1],
        active_stays=active_stays,
        cameras_online=cameras_online,
        cameras_total=cameras_total,
        last_24h=hourly_flow(db),
    )


def daily_report(db: Session, start: datetime, end: datetime) -> list[DailyReportRow]:
    day = func.date_trunc("day", Event.occurred_at).label("day")

    rows = db.execute(
        select(
            day,
            func.count().filter(Event.direction == EventDirection.in_).label("entries"),
            func.count().filter(Event.direction == EventDirection.out).label("exits"),
            func.count(distinct(Event.person_id)).label("unique_people"),
        )
        .where(Event.occurred_at >= start, Event.occurred_at < end)
        .group_by(day)
        .order_by(day)
    ).all()

    report: list[DailyReportRow] = []
    for r in rows:
        # Sample occupancy every 4 hours to approximate the daily average.
        # date_trunc('day') puts r.day at midnight, so hour substitution walks
        # the day: 00:00, 04:00, ... 20:00.
        samples = [current_occupancy(db, r.day.replace(hour=h)).total for h in range(0, 24, 4)]
        report.append(
            DailyReportRow(
                day=r.day,
                entries=r.entries,
                exits=r.exits,
                unique_people=r.unique_people,
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
