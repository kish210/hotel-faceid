"""Catalogue of the image-processing modules an operator can switch on.

Two kinds of module live here:

* **built-in** — the detection code ships with the application and runs on the
  plain CPU using OpenCV only. Nothing to install; switching it on for a camera
  is enough.
* **pack-backed** — the code ships too, but it needs a model file that is far
  too large to bundle (plate reading, for one). Those are downloaded on demand
  into `data/modules/<id>/` from the admin page, and the module only becomes
  usable once its pack is present.

The face-service reads the same catalogue, so a module added here appears in
the panel and in the capture pipeline together.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import requests

from ..config import settings

log = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT = (10.0, 600.0)
MAX_PACK_BYTES = 500 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    id: str
    name: str
    description: str
    version: str
    cpu_cost: str  # light | moderate | heavy
    settings: dict = field(default_factory=dict)
    #: file the pack must contain once unpacked; None for built-in modules
    pack_entry: str | None = None
    pack_url: str | None = None
    pack_size_mb: float | None = None
    pack_sha256: str | None = None


CATALOGUE: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        id="intrusion",
        name="ورود به منطقهٔ ممنوعه",
        description=(
            "هر حرکتی در ناحیهٔ تعیین‌شده (انبار، پشت پیشخوان، درب اضطراری) را "
            "در ساعات دلخواه گزارش می‌کند."
        ),
        version="1.0",
        cpu_cost="light",
        settings={
            "min_area_percent": 1.5,
            "zone": [],  # empty = whole frame; otherwise [[x,y], …] in 0..1
            "active_hours": [],  # empty = always; otherwise [[start, end], …]
            "warmup_frames": 30,  # frames spent learning the empty scene
            "cooldown_seconds": 60,
        },
    ),
    ModuleSpec(
        id="crowd",
        name="تجمع غیرعادی",
        description="وقتی تعداد افراد در کادر از حد تعیین‌شده بیشتر شود هشدار می‌دهد.",
        version="1.0",
        cpu_cost="light",
        settings={"max_people": 5, "sustain_seconds": 10, "cooldown_seconds": 120},
    ),
    ModuleSpec(
        id="fight",
        name="درگیری و نزاع",
        description=(
            "ترکیب حرکت شدید و ناگهانی با نزدیک بودن چند نفر به هم — برای لابی و "
            "راهرو. حساسیت را پایین بیاورید تا هشدار اشتباه کمتر شود."
        ),
        version="1.0",
        cpu_cost="moderate",
        settings={
            "motion_threshold": 0.045,
            "min_people": 2,
            "sustain_seconds": 3,
            "warmup_frames": 30,
            "cooldown_seconds": 120,
        },
    ),
    ModuleSpec(
        id="loitering",
        name="پرسه‌زنی",
        description="فردی که بیش از حد معمول در یک نقطه می‌ماند را گزارش می‌کند.",
        version="1.0",
        cpu_cost="light",
        settings={"seconds": 180, "cooldown_seconds": 300},
    ),
    ModuleSpec(
        id="object_left",
        name="جاگذاشتن یا برداشتن شیء",
        description=(
            "شیئی که بی‌صاحب رها شده یا از جای همیشگی‌اش برداشته شده را تشخیص "
            "می‌دهد — برای چمدان رهاشده و برداشتن وسایل از لابی."
        ),
        version="1.0",
        cpu_cost="moderate",
        settings={"seconds": 45, "min_area_percent": 0.5, "cooldown_seconds": 180},
    ),
    ModuleSpec(
        id="anpr",
        name="پلاک‌خوان خودرو",
        description=(
            "پلاک خودروهای ورودی/خروجی پارکینگ را می‌خواند و ثبت می‌کند. "
            "به بستهٔ مدل نیاز دارد و روی دوربین پارکینگ نصب شود."
        ),
        version="1.0",
        cpu_cost="heavy",
        settings={"min_confidence": 0.55, "cooldown_seconds": 20},
        pack_entry="plate_detector.onnx",
        pack_url="https://github.com/kish210/hotel-faceid/releases/download/packs-v1/anpr-1.0.zip",
        pack_size_mb=48.0,
    ),
)

BY_ID = {spec.id: spec for spec in CATALOGUE}


def modules_root() -> Path:
    """Where downloaded packs live — beside the database, not inside the code."""
    return Path(settings.media_root).parent / "modules"


def pack_dir(module_id: str) -> Path:
    return modules_root() / module_id


def is_installed(spec: ModuleSpec) -> bool:
    """Built-in modules are always ready; pack-backed ones need their file."""
    if spec.pack_entry is None:
        return True
    return (pack_dir(spec.id) / spec.pack_entry).is_file()


class ModuleError(Exception):
    """Raised when a pack cannot be installed."""


def install(spec: ModuleSpec, source_url: str | None = None) -> None:
    """Fetch and unpack a module's model files.

    `source_url` lets an operator point at a file they copied onto the machine
    themselves, which is the escape hatch when the server has no internet.
    """
    if spec.pack_entry is None:
        return

    url = source_url or spec.pack_url
    if not url:
        raise ModuleError("برای این ماژول آدرس دانلودی تعریف نشده است")

    target = pack_dir(spec.id)
    target.mkdir(parents=True, exist_ok=True)
    archive = target / "pack.zip"

    try:
        if url.startswith(("http://", "https://")):
            _download(url, archive)
        else:
            local = Path(url)
            if not local.is_file():
                raise ModuleError(f"فایل پیدا نشد: {url}")
            shutil.copyfile(local, archive)

        with zipfile.ZipFile(archive) as bundle:
            _extract_safely(bundle, target)
    except ModuleError:
        raise
    except Exception as exc:
        log.warning("Installing module %s failed", spec.id, exc_info=True)
        raise ModuleError(f"نصب ماژول ناموفق بود: {exc}") from exc
    finally:
        archive.unlink(missing_ok=True)

    if spec.pack_sha256:
        _verify(target / spec.pack_entry, spec.pack_sha256)

    if not is_installed(spec):
        raise ModuleError("بستهٔ دانلودشده فایل مورد انتظار را نداشت")


def remove(spec: ModuleSpec) -> None:
    if spec.pack_entry is not None:
        shutil.rmtree(pack_dir(spec.id), ignore_errors=True)


def _download(url: str, destination: Path) -> None:
    with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT) as response:
        response.raise_for_status()

        written = 0
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                written += len(chunk)
                if written > MAX_PACK_BYTES:
                    raise ModuleError("حجم بستهٔ دانلودی بیش از حد مجاز است")
                handle.write(chunk)


def _extract_safely(bundle: zipfile.ZipFile, target: Path) -> None:
    """Unpack, refusing entries that would escape the module's own folder."""
    root = target.resolve()
    for member in bundle.namelist():
        destination = (root / member).resolve()
        if not destination.is_relative_to(root):
            raise ModuleError(f"مسیر نامعتبر در بسته: {member}")
    bundle.extractall(root)


def _verify(path: Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        path.unlink(missing_ok=True)
        raise ModuleError("امضای فایل دانلودشده مطابقت ندارد")
