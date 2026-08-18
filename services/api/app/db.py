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


def _add_missing_columns() -> None:
    """Add columns introduced after a database was first created.

    `create_all` only ever creates missing *tables*, so an installation that
    predates a new column keeps running against the old shape until the column
    is added. Every type here is portable between SQLite and Postgres.
    """
    from sqlalchemy import inspect, text

    postgres = engine.dialect.name == "postgresql"
    # The Postgres schema (db/init/001_schema.sql) uses native enum types; the
    # SQLite one stores plain text.
    gender_type = "person_gender" if postgres else "VARCHAR(10)"
    json_type = "JSONB" if postgres else "TEXT"

    additions: dict[str, dict[str, str]] = {
        "persons": {
            "gender": f"{gender_type} NOT NULL DEFAULT 'unknown'",
            "gender_votes": json_type,
            "gender_manual": "BOOLEAN NOT NULL DEFAULT FALSE",
            "age_estimate": "INTEGER",
        },
        "cameras": {
            "model": "TEXT",
            "firmware": "TEXT",
            "serial_number": "TEXT",
        },
    }

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        if postgres and "persons" in tables:
            connection.execute(
                text(
                    "DO $$ BEGIN "
                    "CREATE TYPE person_gender AS ENUM ('male', 'female', 'unknown'); "
                    "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
                )
            )
        if postgres and "cameras" in tables:
            # Brands added after the schema was first created.
            connection.execute(text("ALTER TYPE camera_brand ADD VALUE IF NOT EXISTS 'axis'"))

        for table, columns in additions.items():
            if table not in tables:
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    """Create tables and seed the admin user (SQLite path)."""
    from . import models  # noqa: F401  (register tables with Base.metadata)
    from .security import pwd_context
    from sqlalchemy import select

    Base.metadata.create_all(engine)
    _add_missing_columns()
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