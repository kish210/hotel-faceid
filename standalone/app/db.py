import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import DateTime, TypeDecorator

from .config import settings


class GUID(sa.types.TypeDecorator):
    """Portable UUID column.

    Stored as CHAR(36) text so it works on SQLite, but both ``uuid.UUID`` and
    plain-string lookups (e.g. ``db.get(User, "…")`` from a URL segment) are
    accepted on input, and real UUID objects come back out.
    """

    impl = sa.types.String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None or isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


class UTCDateTime(TypeDecorator):
    """Timezone-normalised timestamps for SQLite (no native tz support).

    Everything is stored as UTC-naive text and comes back timezone-aware UTC,
    so aware datetimes from ``datetime.now().astimezone()`` compare correctly.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


url = settings.database_url
connect_args = {}
if url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(url, pool_pre_ping=True, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()