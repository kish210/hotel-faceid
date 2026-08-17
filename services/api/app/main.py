import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import SessionLocal
from .routers import audit, auth, cameras, dashboard, events, faces, persons, users
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
app.include_router(users.router)
app.include_router(audit.router)

Path(settings.media_root).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_root), name="media")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
