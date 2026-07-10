"""
pdf_report.py
Builds a clean, standard business-style PDF report containing:
  - Title + metadata
  - The narrative written by the Reporter Agent
  - A data preview table
  - Every chart produced inside the E2B sandbox
"""

import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak,
)


def _styles():
    base = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=base["Title"], fontSize=22, spaceAfter=6,
        textColor=colors.HexColor("#12233d"),
    )
    meta_style = ParagraphStyle(
        "Meta", parent=base["BodyText"], fontSize=9.5, textColor=colors.HexColor("#555555"),
    )
    h2 = ParagraphStyle(
        "H2", parent=base["Heading2"], spaceBefore=16, spaceAfter=6,
        textColor=colors.HexColor("#1f3864"),
    )
    body = ParagraphStyle("Body", parent=base["BodyText"], fontSize=10.5, leading=15)
    return title_style, meta_style, h2, body


def build_pdf_report(output_path: str, title: str, query: str, narrative_text: str,
                      charts: list, data_preview=None) -> str:
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )
    title_style, meta_style, h2, body = _styles()
    elements = []

    # --- Cover / header ---
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", meta_style))
    elements.append(Paragraph(f"Query: {query}", meta_style))
    elements.append(Spacer(1, 14))

    # --- Narrative from Reporter Agent ---
    known_headers = {
        "TITLE", "EXECUTIVE SUMMARY", "KEY FINDINGS",
        "CHART INSIGHTS", "RECOMMENDATIONS", "CONCLUSION",
    }
    for raw_line in narrative_text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.upper() in known_headers or (line.isupper() and len(line) < 60):
            elements.append(Paragraph(line.title(), h2))
        else:
            elements.append(Paragraph(line, body))

    # --- Data preview table ---
    if data_preview is not None and len(data_preview) > 0:
        elements.append(PageBreak())
        elements.append(Paragraph("Data Preview", h2))
        preview = data_preview.astype(str)
        table_data = [list(preview.columns)] + preview.values.tolist()
        t = Table(table_data, hAlign="LEFT", repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3864")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f8")]),
        ]))
        elements.append(t)

    # --- Charts ---
    if charts:
        elements.append(PageBreak())
        elements.append(Paragraph("Charts", h2))
        for i, chart_bytes in enumerate(charts, start=1):
            elements.append(Paragraph(f"Chart {i}", h2))
            img_buf = io.BytesIO(chart_bytes)
            elements.append(Image(img_buf, width=15 * cm, height=10 * cm, kind="proportional"))
            elements.append(Spacer(1, 14))

    doc.build(elements)
    return output_path