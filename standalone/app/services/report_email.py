"""Scheduled email report of the previous day's traffic."""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
from . import occupancy
from .stays import TZ

log = logging.getLogger(__name__)

# Where the daily.xlsx is staged before being attached.
STAGING_DIR = Path("/data/media") / "reports"


def _loads() -> str:
    from datetime import date

    return date.today().isoformat()


def _report_filename() -> str:
    return f"daily-report-{_loads()}.xlsx"


def _build_xlsx(db: Session, start: datetime, end: datetime) -> bytes:
    from openpyxl import Workbook

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

    from io import BytesIO

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _send(report_bytes: bytes) -> None:
    if not settings.smtp_host or not settings.report_email_to:
        log.info("Email report not configured; skipping send")
        return

    subject = f"گزارش روزانه تردد هتل — {datetime.now(TZ):%Y-%m-%d}"
    body = (
        "گزارش روزانه تردد مهمانان در فایل پیوست ارسال می‌شود.\n\n"
        "این ایمیل به‌صورت خودکار توسط سامانه هوشمند تشخیص چهره تولید شده است."
    )

    message = MIMEMultipart()
    message["From"] = settings.smtp_from or settings.smtp_username
    message["To"] = settings.report_email_to
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain", "utf-8"))
    message.attach(MIMEApplication(report_bytes, _subtype="xlsx", Name=_report_filename()))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(message["From"], settings.report_email_to.split(","), message.as_string())


def maybe_send_daily_report(db: Session) -> bool:
    """Send the report for *yesterday* once per day at the configured hour."""
    if not settings.email_report_enabled:
        return False
    if not settings.smtp_host or not settings.report_email_to:
        return False

    now = datetime.now(TZ)
    if now.hour != settings.email_report_hour:
        return False

    marker = STAGING_DIR / f"sent-{now:%Y-%m-%d}.marker"
    if marker.exists():
        return False

    try:
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=1)
        report_bytes = _build_xlsx(db, start, end)
        _send(report_bytes)
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        marker.write_text(now.isoformat())
        log.info("Daily report email sent for %s", start.date())
        return True
    except Exception:
        log.exception("Failed to send daily report email")
        return False
