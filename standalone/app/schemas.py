import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import CameraBrand, CameraPurpose, EventDirection, PersonRole, UserRole


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------- auth
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    full_name: str | None = None


# ----------------------------------------------------------------- person
class PersonOut(ORMModel):
    id: uuid.UUID
    display_name: str | None
    role: PersonRole
    room_number: str | None
    phone: str | None
    reference_image: str | None
    first_seen_at: datetime
    last_seen_at: datetime


class PersonUpdate(BaseModel):
    display_name: str | None = None
    role: PersonRole | None = None
    room_number: str | None = None
    phone: str | None = None


class PersonDetail(PersonOut):
    total_nights: int = 0
    present: bool = False
    current_stay_nights: int = 0


class PersonMergeRequest(BaseModel):
    source_id: uuid.UUID = Field(description="Person that will be absorbed and removed")
    target_id: uuid.UUID = Field(description="Person that survives the merge")


# ------------------------------------------------------------------ event
class EventOut(ORMModel):
    id: int
    person_id: uuid.UUID
    camera_id: uuid.UUID | None
    direction: EventDirection
    occurred_at: datetime
    confidence: float | None
    image_path: str | None
    manual: bool


class EventCreate(BaseModel):
    """Posted by an operator to correct a misread direction."""

    person_id: uuid.UUID
    camera_id: uuid.UUID | None = None
    direction: EventDirection
    occurred_at: datetime | None = None


# ------------------------------------------- recognition (from face-service)
class RecognizeRequest(BaseModel):
    """Sent by the face-service for every accepted face detection."""

    embedding: list[float] = Field(min_length=512, max_length=512)
    camera_id: uuid.UUID | None = None
    detected_at: datetime | None = None
    confidence: float | None = None
    quality: float | None = None
    image_base64: str | None = Field(default=None, description="JPEG face crop, base64")
    direction_hint: EventDirection | None = None


class RecognizeResponse(BaseModel):
    person_id: uuid.UUID | None = None
    is_new_person: bool
    similarity: float | None
    event_id: int | None
    direction: EventDirection | None
    debounced: bool = False


# ------------------------------------------------------------------- stay
class StayOut(ORMModel):
    id: uuid.UUID
    person_id: uuid.UUID
    checkin_at: datetime
    checkout_at: datetime | None
    nights: int
    room_number: str | None
    active: bool


class GuestRow(BaseModel):
    person_id: uuid.UUID
    display_name: str | None
    role: PersonRole
    room_number: str | None
    reference_image: str | None
    first_entry: datetime
    last_exit: datetime | None
    nights: int
    present: bool


# ----------------------------------------------------------------- camera
class CameraBase(BaseModel):
    name: str
    brand: CameraBrand = CameraBrand.onvif
    purpose: CameraPurpose = CameraPurpose.bidirectional
    location: str | None = None
    host: str
    port: int = 80
    rtsp_url: str | None = None
    username: str | None = None
    use_device_face_engine: bool = False
    enabled: bool = True


class CameraCreate(CameraBase):
    password: str | None = None


class CameraUpdate(BaseModel):
    name: str | None = None
    brand: CameraBrand | None = None
    purpose: CameraPurpose | None = None
    location: str | None = None
    host: str | None = None
    port: int | None = None
    rtsp_url: str | None = None
    username: str | None = None
    password: str | None = None
    use_device_face_engine: bool | None = None
    enabled: bool | None = None


class CameraOut(ORMModel, CameraBase):
    id: uuid.UUID
    online: bool
    last_seen_at: datetime | None


class CameraStreamConfig(CameraOut):
    """Same as CameraOut but carries the decrypted password — service auth only."""

    password: str | None = None


# -------------------------------------------------------------- dashboard
class OccupancyOut(BaseModel):
    total: int
    guests: int
    staff: int
    visitors: int
    as_of: datetime


class HourBucket(BaseModel):
    hour: datetime
    entries: int
    exits: int


class DashboardOut(BaseModel):
    occupancy: OccupancyOut
    today_entries: int
    today_exits: int
    active_stays: int
    cameras_online: int
    cameras_total: int
    last_24h: list[HourBucket]


class DailyReportRow(BaseModel):
    day: datetime
    entries: int
    exits: int
    unique_people: int
    avg_occupancy: float


class TopGuestRow(BaseModel):
    person_id: uuid.UUID
    display_name: str | None
    reference_image: str | None
    total_nights: int
    visits: int


# -------------------------------------------------------- photo face search
class FaceSearchMatch(BaseModel):
    person_id: uuid.UUID
    display_name: str | None
    role: PersonRole
    room_number: str | None
    reference_image: str | None
    similarity: float
    present: bool = False


class FaceSearchResult(BaseModel):
    source_quality: float | None = None
    matches: list[FaceSearchMatch]


# -------------------------------------------------------------------- users
class UserOut(ORMModel):
    id: uuid.UUID
    username: str
    full_name: str | None
    role: UserRole
    active: bool
    created_at: datetime


class UserCreate(BaseModel):
    username: str
    password: str = Field(min_length=6)
    full_name: str | None = None
    role: UserRole = UserRole.reception
    active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=6)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


# -------------------------------------------------------------------- audit
class AuditLogOut(ORMModel):
    id: int
    user_id: uuid.UUID | None
    action: str
    entity: str | None
    entity_id: str | None
    detail: dict | None
    ip_address: str | None
    created_at: datetime
