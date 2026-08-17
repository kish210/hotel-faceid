"""Persian (RTL) PDF generation for reports using Vazirmatn."""

from __future__ import annotations

import io
from datetime import datetime, timedelta
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from ..config import settings
from . import occupancy
from .stays import TZ

FONT_PATH = Path(__file__).resolve().parent.parent / "fonts" / "Vazirmatn-Regular.ttf"

def _register_font() -> str:
    """Register Vazirmatn once; fall back to a builtin if it is missing."""
    if "Vazir" not in pdfmetrics.getRegisteredFontNames():
        if FONT_PATH.exists():
            pdfmetrics.registerFont(TTFont("Vazir", str(FONT_PATH)))
        else:
            return "Helvetica"
    return "Vazir" if "Vazir" in pdfmetrics.getRegisteredFontNames() else "Helvetica"


def fa(text: str | None) -> str:
    """Reshape + bidi a Persian string for correct RTL rendering."""
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def daily_report_pdf(db: Session, start: datetime | None, end: datetime | None) -> bytes:
    end = end or datetime.now(TZ)
    start = start or end - timedelta(days=30)

    font = _register_font()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    title_style = ParagraphStyle(
        "Title", fontName=font, fontSize=16, alignment=1, spaceAfter=2 * mm
    )
    subtitle_style = ParagraphStyle(
        "Sub", fontName=font, fontSize=10, alignment=1, textColor=colors.grey, spaceAfter=4 * mm
    )
    header_style = ParagraphStyle(
        "Header", fontName=font, fontSize=10, alignment=TA_RIGHT, textColor=colors.white
    )
    cell_style = ParagraphStyle("Cell", fontName=font, fontSize=9, alignment=TA_RIGHT)

    rows = occupancy.daily_report(db, start, end)

    story = [
        Paragraph(fa("گزارش روزانه تردد هتل"), title_style),
        Paragraph(
            fa(f"بازه: {start:%Y-%m-%d} تا {end:%Y-%m-%d} — تعداد روز: {len(rows)}"),
            subtitle_style,
        ),
        Spacer(1, 4 * mm),
    ]

    data = [
        [
            Paragraph(fa("تاریخ"), header_style),
            Paragraph(fa("ورود"), header_style),
            Paragraph(fa("خروج"), header_style),
            Paragraph(fa("افراد یکتا"), header_style),
            Paragraph(fa("میانگین اشغال"), header_style),
        ]
    ]
    for row in rows:
        data.append(
            [
                Paragraph(fa(f"{row.day:%Y-%m-%d}"), cell_style),
                Paragraph(fa(str(row.entries)), cell_style),
                Paragraph(fa(str(row.exits)), cell_style),
                Paragraph(fa(str(row.unique_people)), cell_style),
                Paragraph(fa(f"{row.avg_occupancy:.1f}"), cell_style),
            ]
        )

    table = Table(data, repeatRows=1, colWidths=[42 * mm, 28 * mm, 28 * mm, 34 * mm, 36 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)

    doc.build(story)
    return buffer.getvalue()


def top_guests_pdf(db: Session, limit: int = 20) -> bytes:
    font = _register_font()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    title_style = ParagraphStyle("Title", fontName=font, fontSize=16, alignment=1, spaceAfter=4 * mm)
    header_style = ParagraphStyle(
        "Header", fontName=font, fontSize=10, alignment=TA_RIGHT, textColor=colors.white
    )
    cell_style = ParagraphStyle("Cell", fontName=font, fontSize=9, alignment=TA_RIGHT)

    guests = occupancy.top_guests(db, limit)

    story = [Paragraph(fa("مهمانان با بیشترین شب اقامت"), title_style)]
    data = [
        [
            Paragraph(fa("نام"), header_style),
            Paragraph(fa("شب اقامت"), header_style),
            Paragraph(fa("تعداد مراجعه"), header_style),
        ]
    ]
    for row in guests:
        data.append(
            [
                Paragraph(fa(row.display_name or row.person_id.hex[:8]), cell_style),
                Paragraph(fa(str(row.total_nights)), cell_style),
                Paragraph(fa(str(row.visits)), cell_style),
            ]
        )

    table = Table(data, repeatRows=1, colWidths=[90 * mm, 40 * mm, 40 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)

    doc.build(story)
    return buffer.getvalue()
