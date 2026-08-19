import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import (
    AlertSeverity,
    CameraBrand,
    CameraPurpose,
    EventDirection,
    PersonGender,
    PersonRole,
    UserRole,
)


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
    gender: PersonGender = PersonGender.unknown
    gender_manual: bool = False
    age_estimate: int | None = None
    alarm_enabled: bool = False
    alarm_note: str | None = None
    room_number: str | None
    phone: str | None
    reference_image: str | None
    first_seen_at: datetime
    last_seen_at: datetime


class PersonUpdate(BaseModel):
    display_name: str | None = None
    role: PersonRole | None = None
    gender: PersonGender | None = Field(
        default=None, description="Operator override; stops automatic gender updates"
    )
    alarm_enabled: bool | None = Field(
        default=None, description="Put this person on the watchlist"
    )
    alarm_note: str | None = None
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
    gender: PersonGender | None = Field(default=None, description="Estimated by the face engine")
    age: int | None = Field(default=None, ge=0, le=120, description="Estimated age in years")


class RecognizeResponse(BaseModel):
    person_id: uuid.UUID
    is_new_person: bool
    similarity: float | None
    event_id: int | None
    direction: EventDirection | None
    debounced: bool = False
    gender: PersonGender = PersonGender.unknown
    alarm: bool = Field(default=False, description="This person is on the watchlist")
    alarm_person_name: str | None = None
    alarm_note: str | None = None


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
    gender: PersonGender = PersonGender.unknown
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
    model: str | None = None
    firmware: str | None = None
    serial_number: str | None = None
    purpose: CameraPurpose = CameraPurpose.bidirectional
    location: str | None = None
    host: str
    port: int = 80
    rtsp_url: str | None = None
    username: str | None = None
    use_device_face_engine: bool = False
    analytics: list[str] = Field(
        default_factory=list, description="Ids of the analytics modules to run on this camera"
    )
    analytics_config: dict = Field(default_factory=dict, description="Per-module settings")
    enabled: bool = True

    # Both columns are NULL on rows written before analytics existed.
    @field_validator("analytics", "analytics_config", mode="before")
    @classmethod
    def _null_is_empty(cls, value, info):
        if value is None:
            return [] if info.field_name == "analytics" else {}
        return value


class CameraCreate(CameraBase):
    password: str | None = None
    autodetect: bool = Field(
        default=True,
        description="Probe the device for brand/model before saving, when reachable",
    )


class CameraUpdate(BaseModel):
    name: str | None = None
    brand: CameraBrand | None = None
    analytics: list[str] | None = None
    analytics_config: dict | None = None
    model: str | None = None
    firmware: str | None = None
    serial_number: str | None = None
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


# --------------------------------------------------------- camera autodetect
class CameraProbeRequest(BaseModel):
    """Credentials for a one-off identification request against a device."""

    host: str
    port: int = 80
    username: str | None = None
    password: str | None = None
    camera_id: uuid.UUID | None = Field(
        default=None,
        description="Re-probe a saved camera: its stored password is used when none is given",
    )


class CameraProbeResult(BaseModel):
    detected: bool
    brand: CameraBrand = CameraBrand.generic
    model: str | None = None
    firmware: str | None = None
    serial_number: str | None = None
    rtsp_url: str | None = Field(default=None, description="Suggested main-stream path")
    supports_device_face_engine: bool = False
    detail: str | None = Field(default=None, description="Why detection failed, if it did")


class CameraStreamConfig(CameraOut):
    """Same as CameraOut but carries the decrypted password — service auth only."""

    password: str | None = None


# ------------------------------------------------- analytics alerts
class AlertOut(ORMModel):
    id: int
    camera_id: uuid.UUID | None
    camera_name: str | None = None
    module: str
    module_name: str | None = Field(default=None, description="Display name, resolved by the API")
    severity: AlertSeverity
    title: str
    detail: dict | None
    image_path: str | None
    person_id: uuid.UUID | None
    occurred_at: datetime
    acknowledged_at: datetime | None


class AlertCreate(BaseModel):
    """Posted by the face-service when a module fires."""

    camera_id: uuid.UUID | None = None
    module: str
    severity: AlertSeverity = AlertSeverity.warning
    title: str
    detail: dict | None = None
    image_base64: str | None = Field(default=None, description="JPEG snapshot, base64")
    person_id: uuid.UUID | None = None
    occurred_at: datetime | None = None


# ------------------------------------------------- analytics modules
class AnalyticsModuleOut(BaseModel):
    """One image-processing capability that can be switched on per camera."""

    id: str
    name: str
    description: str
    version: str
    installed: bool
    # False for modules whose code ships with the app and need no model pack.
    needs_pack: bool = False
    pack_size_mb: float | None = None
    cpu_cost: str = Field(description="light | moderate | heavy — guidance for CPU-only servers")
    cameras: int = Field(default=0, description="How many cameras currently run it")
    settings: dict = Field(default_factory=dict, description="Tunables and their defaults")


class ModuleInstallRequest(BaseModel):
    source_url: str | None = Field(
        default=None,
        description="Override the download location, or point at a local file for offline installs",
    )


# -------------------------------------------------------------- dashboard
class OccupancyOut(BaseModel):
    total: int
    guests: int
    staff: int
    visitors: int
    males: int = 0
    females: int = 0
    unknown_gender: int = 0
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
    gender: PersonGender = PersonGender.unknown
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
