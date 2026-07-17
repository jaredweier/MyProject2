# UI sources learnings (any public source)

## 2026-07-09T08:49:49.649751+00:00 — improve-batch
Ctrl+K palette, clickable KPIs, iCal export+legend, bulk reject leave, availability page, 7k hours meter, prefill schedule, period catalog, open-shift digest

## 2026-07-09T08:52:25.655239+00:00 — deep-improve
Notifications inbox, certs admin UI, explainable coverage plan dialog, ops exports CSV/PDF, conflict panel on availability

## 2026-07-09T09:08:00.356324+00:00 — nicegui-aggrid-2026
NiceGUI AG Grid: themes quartz/balham/material/alpine; dark auto; floating filters (agText/agNumberColumnFilter); pagination; cellClassRules; get_selected_rows; export path via rowData snapshot. Dark theme issues exist historically — set theme=quartz + page dark. Chronos tables.py upgraded to quartz + floatingFilter + CSV export helper.
_  https://nicegui.io/documentation/aggrid_

## 2026-07-09T09:08:00.734745+00:00 — dashboard-noc-2026
2026 admin/NOC dashboards: dark mode is functional for ops floors; alert-first severity colors on dark; KPI row at top; high contrast figures; clickable status chips. Chronos: severity_strip + KPI deep-links on dashboard.
_  https://www.fanruan.com/en/blog/top-admin-dashboard-design-ideas-inspiration_

## 2026-07-09T09:08:01.127730+00:00 — dashboard-ux-anatomy
Dashboard anatomy: header/context → KPI cards with weight → status indicators → detail grids. WCAG 4.5:1 text. Severity not only red-green — use cyan info on dark. Applied to Chronos ops severity strip.
_  https://www.setproduct.com/blog/dashboard-ui-design_

## 2026-07-09T09:08:02.371938+00:00 — bryntum-timefold-ui
Bryntum+Timefold blogs: Gantt/timeline for shifts + hard/soft preference solve. Chronos matrix heat board is simpler; keep status legend + sticky officer labels; optional Gantt later.
_  https://bryntum.com/blog/planning-employee-shifts-like-a-pro-with-timefold-and-bryntum/_

## 2026-07-09T09:10:26.598228+00:00 — nicegui-aggrid-api-code
NiceGUI AG Grid written as options={columnDefs,rowData,defaultColDef} + theme prop; floatingFilter column defs; run_grid_method for API; get_selected_rows async; update rowData then grid.update(); cellClassRules for severity CSS; suspend_updates+applyTransaction for edit-safe rows. Chronos gui/tables wraps this — keep business logic out of tables module.
_  https://nicegui.io/documentation/aggrid_

## 2026-07-09T09:20:54.312038+00:00 — eval-ui-stability
After large Chronos UI growth (finance dual FLSA, leave donation, CP-SAT sim, rank candidates): evaluate for broken imports, duplicate handlers, NiceGUI refresh errors, permission gates. No new UI until tests green.

## 2026-07-17T06:39:43.419124+00:00 — nicegui-llms-txt
Official NiceGUI LLM guide: refreshable>clear, bindings in-place, scroll_area+stepper/chips, mark(), skeleton, no module-level state, run.io_bound/to_thread, avoid CSS thrash. Applied to sim + always-on watcher fix.
_  https://nicegui.io/llms.txt_
