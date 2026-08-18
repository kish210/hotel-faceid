import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class PersonRole(str, enum.Enum):
    guest = "guest"
    staff = "staff"
    visitor = "visitor"
    unknown = "unknown"


class CameraBrand(str, enum.Enum):
    dahua = "dahua"
    hikvision = "hikvision"
    axis = "axis"
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
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


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
    room_number: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    reference_image: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    merged_into: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("persons.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    embeddings: Mapped[list["FaceEmbedding"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    events: Mapped[list["Event"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    stays: Mapped[list["Stay"]] = relationship(back_populates="person", cascade="all, delete-orphan")


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id: Mapped[uuid.UUID] = _uuid_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), index=True
    )
    embedding: Mapped[list[float]] = mapped_column(JSON)
    image_path: Mapped[str | None] = mapped_column(Text)
    quality: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

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
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), index=True
    )
    camera_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("cameras.id"))
    direction: Mapped[EventDirection] = mapped_column(_enum(EventDirection, "event_direction"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confidence: Mapped[float | None] = mapped_column(Float)
    image_path: Mapped[str | None] = mapped_column(Text)
    manual: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    person: Mapped[Person] = relationship(back_populates="events")
    camera: Mapped[Camera | None] = relationship()


class Stay(Base):
    __tablename__ = "stays"

    id: Mapped[uuid.UUID] = _uuid_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), index=True
    )
    checkin_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    checkout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    nights: Mapped[int] = mapped_column(Integer, default=0)
    room_number: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    person: Mapped[Person] = relationship(back_populates="stays")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    username: Mapped[str] = mapped_column(String, unique=True)
    full_name: Mapped[str | None] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"), default=UserRole.reception)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(Text)
    entity: Mapped[str | None] = mapped_column(Text)
    entity_id: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
