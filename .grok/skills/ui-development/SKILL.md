---
name: ui-development
description: >
  CustomTkinter UI specialist for Dodgeville PD Scheduler. Use for ui/app.py,
  ui/admin_pages.py, ui/feature_pages.py, ui/login.py, ui/widgets.py, ui/theme.py.
  Covers tab layout, permissions gating, and post-mutation refresh.
---

# UI Development Subagent

## Scope

- `ui/app.py` — main shell, tabs, navigation
- `ui/admin_pages.py` — users, setup wizard, password dialogs (`AdminPageMixin`)
- `ui/feature_pages.py` — reports, department settings
- `ui/login.py` — authentication and forced password change
- `ui/widgets.py`, `ui/theme.py` — reusable components and colors

## Architecture rule

UI calls `logic.*` only. No SQL, no inline business rules. Gate actions with `permissions.role_has_permission()`.

## Tab map

| Tab | Permission hints |
|-----|------------------|
| Dashboard | all roles |
| Base / Updated Schedule | `schedule.base.view`, `schedule.updated.edit` for Assign Coverage |
| Timeline (Gantt) | `schedule.export_own` for iCal |
| Requests / Swaps | `requests.submit`, `requests.approve`, `swaps.*` |
| Officers | `officers.manage` |
| User Accounts | `users.manage` |
| Payroll / Timecard | `payroll.*`, `timecard.*` |
| Simulator | `simulator.use` |
| Reports | `reports.view`, `settings.manage` for dept name |
| Notifications | `notifications.manage` for admin actions |

## Refresh checklist

After mutations, refresh affected widgets:

- Officer CRUD → officer lists, request dropdowns, Gantt officer filter
- Request approve/reject → dashboard stats, Gantt, requests table
- User CRUD → users table
- Manual override → updated schedule + Gantt

## Workflow

1. Confirm logic function exists (`python dev.py feature-map`)
2. Add UI control with existing theme patterns (`DODGEVILLE_*` colors)
3. Wire command to `logic.*`; show success/error via existing dialog patterns
4. Manual smoke: `python main.py` (or note GUI verification for user)
5. Run `python dev.py check`

## Modularization note

Prefer new mixins (`admin_pages.py`, `feature_pages.py` pattern) over growing `app.py` monolith.
