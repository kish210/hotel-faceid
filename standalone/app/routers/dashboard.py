import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_db
from ..models import User
from ..schemas import DailyReportRow, DashboardOut, OccupancyOut, TopGuestRow
from ..security import get_current_user
from ..services import occupancy
from ..services.reports import daily_report_pdf, top_guests_pdf
from ..services.stays import TZ
from ..ws import manager

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DashboardOut:
    return occupancy.dashboard(db)


@router.get("/occupancy", response_model=OccupancyOut)
def get_occupancy(
    at: datetime | None = Query(default=None, description="Historic point in time"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> OccupancyOut:
    """How many people are inside — now, or at any past moment.

    `GET /api/occupancy?at=2026-08-04T23:00:00+03:30` answers
    "how many people were in the hotel at 11pm last night".
    """
    return occupancy.current_occupancy(db, at)


@router.get("/reports/daily", response_model=list[DailyReportRow])
def daily_report(
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[DailyReportRow]:
    end = end or datetime.now(TZ)
    start = start or end - timedelta(days=30)
    return occupancy.daily_report(db, start, end)


@router.get("/reports/top-guests", response_model=list[TopGuestRow])
def top_guests(
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[TopGuestRow]:
    """Guests with the most nights — the loyal/returning ones."""
    return occupancy.top_guests(db, limit)


@router.get("/reports/daily.xlsx")
def daily_report_xlsx(
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StreamingResponse:
    from openpyxl import Workbook

    end = end or datetime.now(TZ)
    start = start or end - timedelta(days=30)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Daily"
    sheet.append(["Date", "Entries", "Exits", "Unique people", "Avg occupancy"])
    for row in occupancy.daily_report(db, start, end):
        sheet.append(
            [
                row.day.strftime("%Y-%m-%d"),
                row.entries,
                row.exits,
                row.unique_people,
                row.avg_occupancy,
            ]
        )

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="daily-report.xlsx"'},
    )


@router.get("/reports/daily.pdf")
def daily_report_pdf_endpoint(
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StreamingResponse:
    content = daily_report_pdf(db, start, end)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="daily-report.pdf"'},
    )


@router.get("/reports/top-guests.pdf")
def top_guests_pdf_endpoint(
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StreamingResponse:
    content = top_guests_pdf(db, limit)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="top-guests.pdf"'},
    )


@router.websocket("/ws")
async def live_updates(websocket: WebSocket) -> None:
    """Pushes `occupancy` and `event` messages as they happen."""
    await manager.connect(websocket)
    try:
        with SessionLocal() as db:
            await websocket.send_json(
                {"type": "occupancy", "payload": occupancy.current_occupancy(db).model_dump(mode="json")}
            )
        while True:
            await websocket.receive_text()  # keep-alive pings from the client
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
