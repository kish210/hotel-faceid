import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import SessionLocal, init_db
from .routers import (
    alerts,
    analytics,
    audit,
    auth,
    cameras,
    dashboard,
    events,
    faces,
    persons,
    users,
)
from .services import report_email, stays, storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)

MAINTENANCE_INTERVAL_SECONDS = 15 * 60


async def _maintenance_loop() -> None:
    """Closes abandoned stays, enforces retention, sends the daily report."""
    while True:
        try:
            with SessionLocal() as db:
                closed = stays.close_stale_stays(db)
                report_email.maybe_send_daily_report(db)
            purged = storage.purge_expired_images()
            if closed or purged:
                log.info("maintenance: closed %d stays, purged %d images", closed, purged)
        except Exception:
            log.exception("maintenance cycle failed")
        await asyncio.sleep(MAINTENANCE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    Path(settings.media_root).mkdir(parents=True, exist_ok=True)
    task = asyncio.create_task(_maintenance_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(
    title="Hotel Face-ID API",
    description="Face recognition based guest identification and occupancy tracking",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(persons.router)
app.include_router(events.router)
app.include_router(cameras.router)
app.include_router(dashboard.router)
app.include_router(faces.router)
app.include_router(alerts.router)
app.include_router(analytics.router)
app.include_router(users.router)
app.include_router(audit.router)

Path(settings.media_root).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_root), name="media")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _web_dist() -> Path:
    """Where the built panel lives: app/ → api/ → services/ → repo root."""
    if settings.web_dist:
        return Path(settings.web_dist)
    return Path(__file__).resolve().parents[3] / "web" / "dist"


# The panel is served by this same process — there is no separate web server.
# Mounted last so it never shadows /api, /media or /health, and only when a
# build exists (during development Vite serves it on port 5173 instead).
_dist = _web_dist()
if (_dist / "index.html").is_file():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")
    log.info("Serving the web panel from %s", _dist)
else:
    log.warning("No web build at %s — run `npm run build` in web/", _dist)
