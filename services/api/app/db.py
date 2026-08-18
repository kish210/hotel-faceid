from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True, connect_args=_connect_args)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables and seed the admin user (SQLite path)."""
    from . import models  # noqa: F401  (register tables with Base.metadata)
    from .security import pwd_context
    from sqlalchemy import select

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        existing = db.scalar(select(models.User).where(models.User.username == "admin"))
        if existing is None:
            db.add(
                models.User(
                    username="admin",
                    full_name="System Administrator",
                    password_hash=pwd_context.hash("admin"),
                    role=models.UserRole.admin,
                    active=True,
                )
            )
            db.commit()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()