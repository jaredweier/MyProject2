"""PDF export helpers using ReportLab."""

import os
from datetime import date
from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from validators import format_date


def _build_doc(output_path: str, title: str, landscape_mode: bool = False):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    pagesize = landscape(letter) if landscape_mode else letter
    doc = SimpleDocTemplate(output_path, pagesize=pagesize, title=title)
    styles = getSampleStyleSheet()
    return doc, styles


def generate_schedule_pdf(
    matrix: List[Dict],
    days: List[date],
    output_path: str,
    title: str = "Dodgeville PD Schedule",
) -> Dict:
    if not matrix or not days:
        return {"success": False, "message": "No schedule data to export"}

    doc, styles = _build_doc(output_path, title, landscape_mode=True)
    story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]

    headers = ["Officer"] + [format_date(d) for d in days]
    rows = [headers]
    for entry in matrix:
        officer = entry["officer"]
        row = [officer["name"][:18]]
        for day in days:
            row.append(entry["days"].get(day, "off"))
        rows.append(row)

    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D1B2A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return {"success": True, "path": output_path}


def generate_payroll_pdf(entries: List[Dict], output_path: str, title: str = "Payroll Ledger") -> Dict:
    if not entries:
        return {"success": False, "message": "No payroll entries to export"}

    doc, styles = _build_doc(output_path, title)
    story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]

    headers = ["Officer", "Date", "Type", "Hours", "Pay", "Bank Δ"]
    rows = [headers]
    for entry in entries:
        bank_parts = []
        for key, label in [
            ("comp_bank_delta", "comp"),
            ("sick_bank_delta", "sick"),
            ("float_holiday_bank_delta", "float"),
            ("holiday_bank_delta", "hol"),
        ]:
            delta = entry.get(key) or 0
            if delta:
                bank_parts.append(f"{label}{delta:+.1f}")
        rows.append(
            [
                entry.get("officer_name", ""),
                format_date(entry["entry_date"]) if entry.get("entry_date") else "",
                entry.get("entry_type", ""),
                f"{entry.get('hours', 0):.1f}",
                f"${entry.get('calculated_pay', 0):,.2f}",
                " ".join(bank_parts) or "—",
            ]
        )

    table = Table(rows, repeatRows=1, colWidths=[120, 70, 110, 45, 60, 80])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D1B2A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return {"success": True, "path": output_path}


def generate_requests_pdf(requests: List[Dict], output_path: str, title: str = "Day-Off Requests") -> Dict:
    if not requests:
        return {"success": False, "message": "No requests to export"}

    doc, styles = _build_doc(output_path, title)
    story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]

    headers = ["ID", "Officer", "Date", "Type", "Status"]
    rows = [headers]
    for req in requests:
        rows.append(
            [
                str(req.get("id", "")),
                req.get("officer_name", ""),
                format_date(req["request_date"]) if req.get("request_date") else "",
                req.get("request_type", ""),
                req.get("status", ""),
            ]
        )

    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D1B2A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return {"success": True, "path": output_path}


def generate_shift_swaps_pdf(
    swaps: List[Dict],
    output_path: str,
    title: str = "Shift Swap Requests",
) -> Dict:
    if not swaps:
        return {"success": False, "message": "No swap requests to export"}

    doc, styles = _build_doc(output_path, title)
    story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]

    headers = ["ID", "Date", "Officer 1", "Officer 2", "Status"]
    rows = [headers]
    for swap in swaps:
        rows.append(
            [
                str(swap.get("id", "")),
                format_date(swap["swap_date"]) if swap.get("swap_date") else "",
                swap.get("officer1_name", ""),
                swap.get("officer2_name", ""),
                swap.get("status", ""),
            ]
        )

    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D1B2A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return {"success": True, "path": output_path}


def generate_coverage_pdf(report: Dict, output_path: str) -> Dict:
    days = report.get("days") or []
    if not days:
        return {"success": False, "message": "No coverage data"}

    start = report.get("start_date", "")
    end = report.get("end_date", "")
    title = f"Coverage Report {format_date(start) if start else ''} – {format_date(end) if end else ''}"
    doc, styles = _build_doc(output_path, title, landscape_mode=True)
    story = [
        Paragraph("Dodgeville Police Department", styles["Title"]),
        Paragraph(title, styles["Heading2"]),
        Paragraph(f"Issues: {report.get('issue_count', 0)}", styles["Normal"]),
        Spacer(1, 12),
    ]

    headers = ["Date", "Cycle", "Squad", "06:00", "10:00", "15:00", "19:00", "Night Risk", "Status"]
    rows = [headers]
    for day in days:
        counts = day.get("shift_counts") or {}
        status = "GAP" if day.get("night_issues") else "OK"
        rows.append(
            [
                format_date(day["date"]) if day.get("date") else "",
                str(day.get("cycle_day", "")),
                day.get("squad_on_duty", ""),
                str(counts.get("06:00", 0)),
                str(counts.get("10:00", 0)),
                str(counts.get("15:00", 0)),
                str(counts.get("19:00", 0)),
                "Yes" if day.get("high_risk_night") else "",
                status,
            ]
        )

    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D1B2A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return {"success": True, "path": output_path}


def generate_pay_stub_pdf(stub: Dict, output_path: str) -> Dict:
    if not stub.get("success"):
        return {"success": False, "message": stub.get("message", "No stub data")}

    officer = stub["officer"]
    title = f"Pay Stub — {officer['name']}"
    doc, styles = _build_doc(output_path, title)
    story = [
        Paragraph("Dodgeville Police Department", styles["Title"]),
        Paragraph(title, styles["Heading2"]),
        Spacer(1, 8),
        Paragraph(
            f"Pay period: {format_date(stub['period_start'])} to {format_date(stub['period_end'])}",
            styles["Normal"],
        ),
        Paragraph(f"Hourly rate: ${stub['hourly_rate']:.2f}", styles["Normal"]),
        Spacer(1, 12),
    ]

    summary = [
        ["Category", "Hours", "Amount"],
        ["Regular", f"{stub['regular_hours']:.1f}", "—"],
        ["Other", f"{stub['other_hours']:.1f}", "—"],
        ["Gross Pay", f"{stub['total_hours']:.1f}", f"${stub['gross_pay']:,.2f}"],
    ]
    table = Table(summary, colWidths=[140, 80, 100])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D1B2A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E8EEF7")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ]
        )
    )
    story.append(table)

    rows = stub.get("payroll_rows") or []
    if rows:
        story.append(Spacer(1, 16))
        story.append(Paragraph("Payroll line items", styles["Heading3"]))
        detail = [["Date", "Type", "Hours", "Pay"]]
        for row in rows:
            detail.append(
                [
                    format_date(row["entry_date"]) if row.get("entry_date") else "",
                    row.get("entry_type", ""),
                    f"{row.get('hours', 0):.1f}",
                    f"${row.get('calculated_pay', 0):,.2f}",
                ]
            )
        dtable = Table(detail, repeatRows=1, colWidths=[80, 130, 50, 70])
        dtable.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#152232")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]
            )
        )
        story.append(dtable)

    doc.build(story)
    return {"success": True, "path": output_path}
