"""Catalogue of the image-processing modules an operator can switch on.

The list itself lives in `modules/catalogue.json` at the root of the project
rather than in this file, so a module can be added or re-described without
shipping a new build. `refresh_catalogue()` re-reads it from the git repository,
which is what the admin page's "check for new modules" does.

Two kinds of module appear there:

* **built-in** — the detection code ships with the application and runs on the
  plain CPU using OpenCV only. Nothing to install; switching it on for a camera
  is enough.
* **pack-backed** — the code ships too, but it needs a model file too large to
  bundle (plate reading, for one). Those are downloaded on demand into
  `data/modules/<id>/`, and the module only becomes usable once its pack is
  present.

A module in the catalogue that this build has no code for is still listed, so
the panel can say "به‌روزرسانی لازم است" instead of silently hiding it.
"""

from __future__ import annotations

import hashlib
import json
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

    @classmethod
    def from_json(cls, entry: dict) -> ModuleSpec:
        return cls(
            id=entry["id"],
            name=entry.get("name", entry["id"]),
            description=entry.get("description", ""),
            version=str(entry.get("version", "1.0")),
            cpu_cost=entry.get("cpu_cost", "light"),
            settings=entry.get("settings", {}),
            pack_entry=entry.get("pack_entry"),
            pack_url=entry.get("pack_url"),
            pack_size_mb=entry.get("pack_size_mb"),
            pack_sha256=entry.get("pack_sha256"),
        )


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


def catalogue_path() -> Path:
    """The catalogue shipped with this installation.

    A copy downloaded from the repository is preferred, because that is how a
    module added after this build was made becomes visible.
    """
    downloaded = modules_root() / "catalogue.json"
    if downloaded.is_file():
        return downloaded

    if settings.module_catalogue:
        return Path(settings.module_catalogue)
    # services/api/app/services/… → the project root, where modules/ lives.
    return Path(__file__).resolve().parents[4] / "modules" / "catalogue.json"


def _load_catalogue() -> tuple[ModuleSpec, ...]:
    path = catalogue_path()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        return tuple(ModuleSpec.from_json(entry) for entry in document["modules"])
    except FileNotFoundError:
        log.warning("Module catalogue not found at %s", path)
    except (ValueError, KeyError, TypeError):
        log.warning("Module catalogue at %s is malformed", path, exc_info=True)
    return ()


#: Loaded once at import; `refresh_catalogue()` replaces it in place.
CATALOGUE: tuple[ModuleSpec, ...] = _load_catalogue()
BY_ID: dict[str, ModuleSpec] = {spec.id: spec for spec in CATALOGUE}


def reload_catalogue() -> None:
    """Re-read the catalogue from disk, keeping BY_ID and CATALOGUE in step."""
    global CATALOGUE, BY_ID
    CATALOGUE = _load_catalogue()
    BY_ID = {spec.id: spec for spec in CATALOGUE}


def refresh_catalogue(source_url: str | None = None) -> int:
    """Fetch the module list from the repository and adopt it.

    Returns how many modules the new catalogue holds. The download is written
    only after it parses, so a broken or truncated response leaves the working
    catalogue alone.
    """
    url = source_url or settings.module_registry_url
    if not url:
        raise ModuleError("آدرس مخزن ماژول‌ها تنظیم نشده است")

    try:
        response = requests.get(url, headers=_registry_headers(), timeout=(10.0, 60.0))
        response.raise_for_status()
        document = response.json()
        modules = [ModuleSpec.from_json(entry) for entry in document["modules"]]
    except requests.RequestException as exc:
        raise ModuleError(f"دریافت فهرست ماژول‌ها ناموفق بود: {exc}") from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise ModuleError("فهرست دریافت‌شده معتبر نبود") from exc

    if not modules:
        raise ModuleError("فهرست دریافت‌شده خالی بود")

    destination = modules_root() / "catalogue.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(response.text, encoding="utf-8")
    reload_catalogue()
    return len(modules)


def _registry_headers() -> dict[str, str]:
    """Auth for a private repository, when a token has been configured."""
    if settings.module_registry_token:
        return {"Authorization": f"token {settings.module_registry_token}"}
    return {}


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
            _download(url, archive, headers=_registry_headers())
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


def _download(url: str, destination: Path, headers: dict[str, str] | None = None) -> None:
    with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT, headers=headers or {}) as response:
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
