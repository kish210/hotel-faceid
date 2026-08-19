import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import GUID, Base, UTCDateTime


class PersonRole(str, enum.Enum):
    guest = "guest"
    staff = "staff"
    visitor = "visitor"
    unknown = "unknown"


class CameraBrand(str, enum.Enum):
    dahua = "dahua"
    hikvision = "hikvision"
    axis = "axis"
    foscam = "foscam"
    onvif = "onvif"
    generic = "generic"


class PersonGender(str, enum.Enum):
    male = "male"
    female = "female"
    unknown = "unknown"


class CameraPurpose(str, enum.Enum):
    entry = "entry"
    exit = "exit"
    bidirectional = "bidirectional"
    monitor = "monitor"


class EventDirection(str, enum.Enum):
    in_ = "in"
    out = "out"


class UserRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    reception = "reception"
    security = "security"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(GUID, primary_key=True, default=uuid.uuid4)


def _autoincrement_pk() -> Mapped[int]:
    """Auto-numbering primary key that works on both engines.

    SQLite only auto-assigns rowids to a column declared exactly `INTEGER
    PRIMARY KEY`; a BIGINT one is left NULL and the insert fails. Postgres
    keeps BIGSERIAL, matching db/init/001_schema.sql.
    """
    return mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )


def _enum(enum_cls, name: str) -> Enum:
    # native_enum=False keeps the schema portable across SQLite and Postgres.
    return Enum(enum_cls, name=name, native_enum=False, values_callable=lambda e: [i.value for i in e])


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[uuid.UUID] = _uuid_pk()
    display_name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[PersonRole] = mapped_column(_enum(PersonRole, "person_role"), default=PersonRole.unknown)
    gender: Mapped[PersonGender] = mapped_column(
        _enum(PersonGender, "person_gender"), default=PersonGender.unknown
    )
    # Per-class tally, e.g. {"male": 12, "female": 3}: the winning class becomes
    # `gender`. Keeping the tally is what makes a single bad frame harmless.
    gender_votes: Mapped[dict | None] = mapped_column(JSON)
    # Set once an operator picks a gender by hand — detections stop overriding it.
    gender_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    age_estimate: Mapped[int | None] = mapped_column(Integer)
    # Watchlist: raise an alarm whenever this person is recognised again.
    alarm_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    alarm_note: Mapped[str | None] = mapped_column(Text)
    room_number: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    reference_image: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    merged_into: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("persons.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())

    embeddings: Mapped[list["FaceEmbedding"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    events: Mapped[list["Event"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    stays: Mapped[list["Stay"]] = relationship(back_populates="person", cascade="all, delete-orphan")


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id: Mapped[uuid.UUID] = _uuid_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("persons.id", ondelete="CASCADE"), index=True
    )
    embedding: Mapped[list[float]] = mapped_column(JSON)
    image_path: Mapped[str | None] = mapped_column(Text)
    quality: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())

    person: Mapped[Person] = relationship(back_populates="embeddings")


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    brand: Mapped[CameraBrand] = mapped_column(_enum(CameraBrand, "camera_brand"), default=CameraBrand.onvif)
    # Filled in by the auto-detect probe (or by hand): "DS-2CD2143G0-I", "P3245-LVE"…
    model: Mapped[str | None] = mapped_column(Text)
    firmware: Mapped[str | None] = mapped_column(Text)
    serial_number: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[CameraPurpose] = mapped_column(
        _enum(CameraPurpose, "camera_purpose"), default=CameraPurpose.bidirectional
    )
    location: Mapped[str | None] = mapped_column(Text)
    host: Mapped[str] = mapped_column(Text)
    port: Mapped[int] = mapped_column(Integer, default=80)
    rtsp_url: Mapped[str | None] = mapped_column(Text)
    username: Mapped[str | None] = mapped_column(Text)
    password_enc: Mapped[str | None] = mapped_column(Text)
    use_device_face_engine: Mapped[bool] = mapped_column(Boolean, default=False)
    # Ids of the analytics modules running on this camera, e.g.
    # ["intrusion", "fight"]. Empty means face recognition only.
    analytics: Mapped[list | None] = mapped_column(JSON)
    # Per-camera module settings, keyed by module id (sensitivity, zone…).
    analytics_config: Mapped[dict | None] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = _autoincrement_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("persons.id", ondelete="CASCADE"), index=True
    )
    camera_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("cameras.id"))
    direction: Mapped[EventDirection] = mapped_column(_enum(EventDirection, "event_direction"))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    confidence: Mapped[float | None] = mapped_column(Float)
    image_path: Mapped[str | None] = mapped_column(Text)
    manual: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())

    person: Mapped[Person] = relationship(back_populates="events")
    camera: Mapped[Camera | None] = relationship()


class AlertSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class Alert(Base):
    """Something an analytics module noticed on a camera.

    Kept apart from `events`: an event is a person crossing the door, an alert
    is a situation somebody should look at — a fight, a plate, an intrusion.
    """

    __tablename__ = "alerts"

    id: Mapped[int] = _autoincrement_pk()
    camera_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("cameras.id"), index=True)
    # Module that raised it: "fight", "anpr", "intrusion"…
    module: Mapped[str] = mapped_column(Text, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(
        _enum(AlertSeverity, "alert_severity"), default=AlertSeverity.warning
    )
    title: Mapped[str] = mapped_column(Text)
    # Module-specific payload: plate text, person count, zone name…
    detail: Mapped[dict | None] = mapped_column(JSON)
    image_path: Mapped[str | None] = mapped_column(Text)
    person_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("persons.id", ondelete="SET NULL"))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now(), index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())

    camera: Mapped[Camera | None] = relationship()


class Stay(Base):
    __tablename__ = "stays"

    id: Mapped[uuid.UUID] = _uuid_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("persons.id", ondelete="CASCADE"), index=True
    )
    checkin_at: Mapped[datetime] = mapped_column(UTCDateTime)
    checkout_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    nights: Mapped[int] = mapped_column(Integer, default=0)
    room_number: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())

    person: Mapped[Person] = relationship(back_populates="stays")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    username: Mapped[str] = mapped_column(String, unique=True)
    full_name: Mapped[str | None] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"), default=UserRole.reception)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = _autoincrement_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(Text)
    entity: Mapped[str | None] = mapped_column(Text)
    entity_id: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
