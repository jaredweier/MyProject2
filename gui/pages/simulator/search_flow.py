"""Search-flow UI extracted from page.py.

Callbacks are invoked at click time so the simulator's late-bound state and
summary handlers remain authoritative.
"""

from __future__ import annotations

import asyncio


def open_search_plan_dialog(ui, *, estimate, kwargs, require_hard_ok, understood_lines, on_run):
    with (
        ui.dialog() as dialog,
        ui.card()
        .classes("q-pa-md")
        .style(
            "min-width:22rem;max-width:32rem;background:#0C1A2E;color:#E8EDF4;border:1px solid rgba(234,179,8,0.45)"
        ),
    ):
        smart = bool(estimate.get("cpsat_eligible"))
        title = "Search Plan" if smart else "Large Search Space"
        title_color = "#93C5FD" if smart else "#FDE68A"
        ui.label(title).style(f"font-size:1.1rem;font-weight:700;color:{title_color}")
        ui.label(estimate.get("warning") or "").style(
            "color:#9AABC4;margin:12px 0;line-height:1.45;white-space:pre-wrap"
        )
        ui.label("Simulator understood").style("font-weight:700;color:#E8EDF4;margin-top:8px")
        ui.label("\n".join(understood_lines)).style("color:#9AABC4;line-height:1.45;white-space:pre-wrap")

        async def _go():
            dialog.close()
            await asyncio.sleep(0.05)
            await on_run(dict(kwargs), bool(require_hard_ok))

        def _stop():
            dialog.close()
            ui.notify("Search cancelled - lock more constraints to shrink space", type="info")

        run_label = "Run Smart Search (Recommended)" if smart else "Run Full Search Anyway"
        with ui.row().classes("gap-2 flex-wrap"):
            ui.button(run_label, on_click=_go).classes("btn-primary").props("no-caps unelevated")
            ui.button("Cancel", on_click=_stop).classes("btn-ghost").props("no-caps outline")
    dialog.open()
