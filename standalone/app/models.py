import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, GUID, UTCDateTime, utcnow


class PersonRole(str, enum.Enum):
    guest = "guest"
    staff = "staff"
    visitor = "visitor"
    unknown = "unknown"


class CameraBrand(str, enum.Enum):
    dahua = "dahua"
    hikvision = "hikvision"
    onvif = "onvif"
    generic = "generic"


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


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[uuid.UUID] = _uuid_pk()
    display_name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[PersonRole] = mapped_column(
        Enum(PersonRole, name="person_role", values_callable=lambda e: [i.value for i in e]),
        default=PersonRole.unknown,
    )
    room_number: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    reference_image: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    merged_into: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("persons.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

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
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    person: Mapped[Person] = relationship(back_populates="embeddings")


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    brand: Mapped[CameraBrand] = mapped_column(
        Enum(CameraBrand, name="camera_brand", values_callable=lambda e: [i.value for i in e]),
        default=CameraBrand.onvif,
    )
    purpose: Mapped[CameraPurpose] = mapped_column(
        Enum(CameraPurpose, name="camera_purpose", values_callable=lambda e: [i.value for i in e]),
        default=CameraPurpose.bidirectional,
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
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("persons.id", ondelete="CASCADE"), index=True
    )
    camera_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("cameras.id"))
    direction: Mapped[EventDirection] = mapped_column(
        Enum(EventDirection, name="event_direction", values_callable=lambda e: [i.value for i in e])
    )
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    confidence: Mapped[float | None] = mapped_column(Float)
    image_path: Mapped[str | None] = mapped_column(Text)
    manual: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    person: Mapped[Person] = relationship(back_populates="events")
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
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    person: Mapped[Person] = relationship(back_populates="stays")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    username: Mapped[str] = mapped_column(String, unique=True)
    full_name: Mapped[str | None] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [i.value for i in e]),
        default=UserRole.reception,
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(Text)
    entity: Mapped[str | None] = mapped_column(Text)
    entity_id: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

