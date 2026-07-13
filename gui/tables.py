"""
Chronos data-table helpers — NiceGUI AG Grid (built-in).

Patterns drawn from NiceGUI/AG Grid docs + enterprise ops dashboards:
  floating filters, dense dark themes, CSV export of visible ledgers.

Docs: https://nicegui.io/documentation/aggrid
Keep business rules out of this module.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from nicegui import ui

ROOT = Path(__file__).resolve().parent.parent
EXPORTS = ROOT / "exports"


def rows_to_column_defs(
    rows: Sequence[Dict[str, Any]],
    *,
    prefer: Optional[Sequence[str]] = None,
    floating_filter: bool = True,
) -> List[Dict[str, Any]]:
    """Build AG Grid columnDefs from dict rows (sortable/filterable enterprise defaults)."""
    if not rows:
        keys = list(prefer or [])
    else:
        keys = list(prefer) if prefer else list(rows[0].keys())
        for row in rows:
            for k in row.keys():
                if k not in keys:
                    keys.append(k)
    defs: List[Dict[str, Any]] = []
    for k in keys:
        field = str(k)
        # Heuristic filter types (NiceGUI/AG Grid mini-filter pattern)
        sample = None
        for row in rows:
            if field in row and row[field] not in (None, ""):
                sample = row[field]
                break
        if isinstance(sample, (int, float)) and not isinstance(sample, bool):
            filt = "agNumberColumnFilter"
        else:
            filt = "agTextColumnFilter"
        col: Dict[str, Any] = {
            "field": field,
            "headerName": field.replace("_", " ").title(),
            "filter": filt,
            "sortable": True,
            "resizable": True,
        }
        if floating_filter:
            col["floatingFilter"] = True
        defs.append(col)
    return defs


def _clean_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    clean: List[Dict[str, Any]] = []
    for row in rows:
        clean.append({str(k): ("" if v is None else v) for k, v in dict(row).items()})
    return clean


def aggrid_from_dicts(
    rows: Sequence[Dict[str, Any]],
    *,
    prefer_columns: Optional[Sequence[str]] = None,
    height: str = "420px",
    theme: str = "quartz",
    dom_layout: str = "normal",
    floating_filter: bool = True,
    page_size: int = 25,
    csv_export: bool = False,
    csv_name: str = "chronos_export",
) -> ui.aggrid:
    """
    Render a filterable/sortable grid. Returns the aggrid element for refresh.

    theme: NiceGUI supports quartz|balham|material|alpine (dark follows page dark mode).
    csv_export: show a button that writes filtered-friendly snapshot of current rowData to exports/.
    """
    clean = _clean_rows(rows)
    options = {
        "columnDefs": rows_to_column_defs(clean, prefer=prefer_columns, floating_filter=floating_filter),
        "rowData": clean,
        "defaultColDef": {
            "flex": 1,
            "minWidth": 88,
            "filter": True,
            "sortable": True,
            "resizable": True,
            "floatingFilter": floating_filter,
        },
        "pagination": True,
        "paginationPageSize": page_size,
        "paginationPageSizeSelector": [10, 25, 50, 100],
        "animateRows": True,
        "domLayout": dom_layout,
        "suppressMenuHide": True,
        "enableCellTextSelection": True,
        "ensureDomOrder": True,
    }
    grid = ui.aggrid(options, theme=theme).classes("w-full chronos-aggrid").style(f"height: {height}")

    if csv_export:

        def do_csv():
            data = grid.options.get("rowData") or []
            path = write_dicts_csv(data, stem=csv_name)
            ui.notify(f"CSV written: {path}", type="positive")

        ui.button("Export grid CSV", on_click=do_csv).classes("btn-ghost q-mt-xs").props("no-caps outline dense")
    return grid


def write_dicts_csv(rows: Sequence[Dict[str, Any]], *, stem: str = "export") -> Path:
    """Write rows to exports/<stem>_<timestamp>.csv — supervisor report pattern."""
    EXPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)[:48] or "export"
    path = EXPORTS / f"{safe}_{stamp}.csv"
    clean = _clean_rows(rows)
    if not clean:
        path.write_text("", encoding="utf-8")
        return path
    # stable header union
    headers: List[str] = []
    for row in clean:
        for k in row.keys():
            if k not in headers:
                headers.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        for row in clean:
            w.writerow(row)
    return path


def refresh_aggrid(
    grid: ui.aggrid,
    rows: Sequence[Dict[str, Any]],
    *,
    prefer_columns: Optional[Sequence[str]] = None,
) -> None:
    """Push new rowData into an existing grid."""
    clean = _clean_rows(rows)
    grid.options["rowData"] = clean
    if prefer_columns or not grid.options.get("columnDefs"):
        grid.options["columnDefs"] = rows_to_column_defs(clean, prefer=prefer_columns)
    grid.update()


def severity_strip(
    items: Sequence[Dict[str, Any]],
    *,
    title: str = "Ops severity",
) -> None:
    """
    Command-center severity strip (dark NOC pattern).
    Each item: {label, count, level: 'ok'|'warn'|'crit'|'info', path?: str}
    """
    ui.label(title).classes("text-xs text-gray-500 q-mb-xs")
    with ui.row().classes("gap-2 flex-wrap q-mb-sm"):
        for it in items:
            level = (it.get("level") or "info").lower()
            count = it.get("count", 0)
            label = it.get("label") or ""
            path = it.get("path")
            if level in ("crit", "critical", "danger") and count:
                color, border = "rgba(239,68,68,0.2)", "rgba(239,68,68,0.55)"
            elif level in ("warn", "warning") and count:
                color, border = "rgba(245,158,11,0.15)", "rgba(245,158,11,0.5)"
            elif level in ("ok", "success"):
                color, border = "rgba(34,197,94,0.12)", "rgba(34,197,94,0.4)"
            else:
                color, border = "rgba(34,211,238,0.1)", "rgba(34,211,238,0.3)"
            style = (
                f"padding:8px 12px;border-radius:10px;background:{color};"
                f"border:1px solid {border};cursor:{'pointer' if path else 'default'};min-width:96px"
            )

            def make_click(p=path):
                if p:
                    return lambda _e=None: ui.navigate.to(p)
                return None

            el = ui.element("div").style(style)
            if path:
                el.on("click", make_click())
            with el:
                ui.html(
                    f'<div style="font-size:10px;letter-spacing:0.06em;color:#9aabc4">{label}</div>'
                    f'<div style="font-size:18px;font-weight:700;color:#f0f4fc">{count}</div>',
                    sanitize=False,
                )
