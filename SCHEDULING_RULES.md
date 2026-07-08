# Dodgeville PD — Scheduling Rules

**Purpose:** Department source of truth for how the scheduler *should* behave.
**Status:** Aligned with department policy (2026-07-07). Code: `config.py`, `validators.py`, `logic/scheduling.py`.

When you change a rule here, tell the dev/agent to update `config.py` / `validators.py` / `logic.py` and add a regression test.

---

## 1. Rotation

| Rule | Current implementation | Confirm? |
|------|------------------------|----------|
| Cycle length | **14 days**, repeating | ☐ |
| Rotation anchor | **2026-06-28** = Cycle Day 1 (`config.ROTATION_BASE_DATE`) | ☐ |
| Dates before anchor | **Rejected** for day-off requests | ☐ |
| Squad A works cycle days | **1, 2, 5, 6, 7, 10, 11** | ☐ |
| Squad B works cycle days | All other days (3, 4, 8, 9, 12, 13, 14) | ☐ |
| Patrol officer “working” | Officer’s squad matches squad on duty that day (rotation; overrides handled separately) | ☑ |
| **Command staff** (Chief, Lieutenant) | **Monday–Friday** by default; not on the A/B patrol rotation | ☑ |
| Command staff exceptions | Manual schedule rows, manual coverage overrides, or roster edits may change any day | ☑ |

**Notes:**

```
Patrol squads A/B follow the 14-day rotation.
Command staff (Chief, Lieutenant) appear as Working Mon–Fri in base schedules.
Supervisors may adjust command staff days via manual monthly schedule edits or coverage overrides.
```

---

## 2. Shifts

| Shift # | Start | End | Night shift? |
|---------|-------|-----|--------------|
| 1 | 06:00 | 17:00 | No |
| 2 | 10:00 | 21:00 | No |
| 3 | 15:00 | 02:00 | **Yes** |
| 4 | 19:00 | 06:00 | **Yes** |

- Each officer has a fixed home shift (`shift_start` / `shift_end` on roster).
- **CONFIRM:** Can officers change shifts mid-cycle? How are shift changes recorded?

---

## 3. Day-off requests

### Who may request

| Rule | Current implementation | Confirm? |
|------|------------------------|----------|
| Active officers only | Yes | ☐ |
| Must be scheduled **working** that day | **No at submit** — off-rotation requests allowed; supervisor approves/denies | ☑ |
| Blackout dates | **Advisory only** — submission allowed; flagged for supervisor review | ☑ |
| One open request per officer per date | **Yes** — blocks if status is `Pending` **or** `Pending Manual Review` | ☑ |
| Request types | Vacation, Sick, Personal, Comp Time, Bereavement, **Training**, **Court** | ☑ |

**CONFIRM:** Officers submit freely; supervisors use **Bulk Approve Auto-OK**, individual approve, or reject.

### Request workflow

```
Officer submits → Pending
       ↓
Supervisor Approve
       ↓
   ┌── Bump OK? ──No──→ Pending Manual Review ──Supervisor Approve──→ Approved (override)
   │                         ↑                              (supervisor override; skips auto bump gate)
   └── Yes ──────────────→ Approved (override + replacement if found)

Supervisor Reject (from Pending or Pending Manual Review) → Rejected (terminal)
```

| Status | Meaning | Supervisor actions |
|--------|---------|-------------------|
| `Pending` | Awaiting decision | Approve, Reject |
| `Pending Manual Review` | Auto bump check failed (night minimum, no replacement, etc.) | Approve (override), Reject |
| `Approved` | Final — override recorded | None |
| `Rejected` | Final | None |

- **Re-approve / re-reject** of terminal requests: **blocked**.
- Approve uses a **single transaction**: if schedule override insert fails, request stays `Pending`.

**CONFIRM:** When supervisor force-approves manual review with **no replacement**, is that allowed? (Code allows it — override with `replacement_officer_id = NULL`.)

---

## 4. Bumping (coverage when someone is off)

### Replacement selection

| Rule | Current implementation | Confirm? |
|------|------------------------|----------|
| Same squad only | Yes | ☑ |
| **On-duty only** — scheduled working that day | Yes — off-rotation and off-day officers excluded | ☑ |
| **Command staff excluded** (Chief, Lieutenant) | Yes — not in auto bump/coverage pool | ☑ |
| Junior bumps first | `ORDER BY seniority_rank DESC` (higher rank number = more junior) | ☐ |
| Replacement must be on an **allowed shift** per bump table | Yes (`config.BUMP_RULES`) | ☐ |
| Already bumped/covering that day | Excluded | ☐ |

### Bump table (shift number → allowed replacement shift numbers)

| Requesting shift | May bump from shifts |
|------------------|----------------------|
| 1 (06:00) | 2, 3 |
| 2 (10:00) | 1, 3 |
| 3 (15:00) | 2, 4 |
| 4 (19:00) | 3 |

**CONFIRM:** Is this table complete and accurate for Dodgeville PD?

### Night minimum (high-risk nights)

| Rule | Current implementation | Confirm? |
|------|------------------------|----------|
| High-risk nights | **Friday and Saturday** only | ☐ |
| Applies to | **Night shifts only** (15:00, 19:00 start) | ☐ |
| Minimum officers on shift | **2** (`NIGHT_MINIMUM_OFFICERS`) | ☐ |
| If approve would drop below minimum **and no replacement is found** | Route to **Pending Manual Review** | ☑ |
| If a valid **on-duty** replacement is found and cascade completes | **Auto-approve** — supervisor review not required | ☑ |

Day shifts on Fri/Sat are **not** subject to night minimum.

### Known gaps (resolved in app — confirm policy)

- [x] **Cascading bump** — `plan_bump_chain` / `suggest_bump_chain` model multi-step coverage; incomplete chains route to **Pending Manual Review**.
- [x] **Covered shift** — `schedule_overrides.covered_shift_start` records which shift slot is covered; staffing counts use this field (falls back to replacement's assigned shift when null).

**Your policy on cascading bumps:**

```
(e.g. "Must always backfill the replacement's shift" / "Supervisor handles manually" / etc.)
```

---

## 5. Shift swaps

| Rule | Current implementation | Confirm? |
|------|------------------------|----------|
| Both officers must be working that day | Validated | ☐ |
| No swap if either officer has override that day | Validated | ☐ |
| Fri/Sat night minimum | Same rules as bumping; may require manual review | ☐ |
| After validation | Stored as `Pending` in `shift_swaps` table | ☐ |

**IMPLEMENTED:** Swap request, approve/reject, dual schedule overrides, UI tab, notifications.

**CONFIRM:** Intended swap behavior when approved:

```
(e.g. exchange squads for one day only? exchange shifts? supervisor must approve both officers?)
```

---

## 6. Schedule display (Gantt / Monthly)

| Display state | Meaning |
|---------------|---------|
| `working` | On rotation, squad on duty, not bumped |
| `off` | Squad off duty |
| `bumped` | Original officer — day off approved |
| `covering` | Replacement officer covering someone else |

- Gantt shows **current 14-day cycle** window.
- Monthly view shows squad on duty and headcount per day.

---

## 7. Payroll

### Entry types (UI)

Overtime Earned, Comp Earned, Comp Taken, Holiday Pay, Holiday Overtime, Sick Time Used, Bereavement, Training, Unpaid, Float Holiday Taken

### Pay calculation (current code)

| Entry type | Multiplier / rule |
|------------|-------------------|
| Overtime Earned | 1.5× base rate |
| Holiday Pay | 2.5× base rate |
| Holiday Overtime | 3.0× base rate (checkbox) |
| Night differential | Added as `hours × (base_rate + night_differential_rate)` |
| **All other types** | **Regular 1.0× base rate** (likely wrong — needs policy) |

**CONFIRM:** Fill in correct pay rules:

| Type | Should pay as |
|------|----------------|
| Comp Earned | |
| Comp Taken | |
| Sick Time Used | |
| Bereavement | |
| Training | |
| Unpaid | |
| Float Holiday Taken | |

---

## 8. Notifications

**IMPLEMENTED:** In-app notifications on day-off submit/approve/reject, manual coverage, shift swaps; Notifications tab with read/mark-all.

**CONFIRM:** Who gets notified, when, and how?

| Event | Notify whom? | Channel? |
|-------|--------------|----------|
| Request submitted | | |
| Request approved | | |
| Request rejected | | |
| Assigned as bump replacement | | |
| Shift swap requested | | |

---

## 9. Roster & admin

| Rule | Current implementation | Confirm? |
|------|------------------------|----------|
| Squads | A or B | ☐ |
| Seniority rank | Lower number = more senior | ☐ |
| Inactive officers | Hidden from active lists; remain in DB | ☐ |
| Officer photos | Optional; stored under app data `photos/` | ☐ |
| Default pay rate | $30.00/hr (seed data varies by rank) | ☐ |
| Night differential rate | Per officer in DB; **not editable in UI yet** | ☐ |

**CONFIRM:** Expected roster size, rank structure, and whether command staff follow the same rotation.

---

## 10. Test scenarios (for regression)

Use these when validating changes. Dates assume rotation base **2026-06-28**.

| ID | Scenario | Expected |
|----|----------|----------|
| S-01 | Squad B officer requests off on **2026-06-28** (Squad A day) | Accepted as `Pending` (off-rotation allowed at submit) |
| S-02 | Squad A officer requests off on **2026-06-28** | Accepted as `Pending` |
| S-03 | Approve same request twice | Second approve fails; one override only |
| S-04 | Day shift (06:00) bump on **Friday 2026-07-03** | Not blocked by night minimum |
| S-05 | Night shift (19:00) approve on **Friday 2026-07-03** when replacement found | → **Approved** (auto) |
| S-06 | Squad off day — no on-duty replacement on approve | → **Pending Manual Review**, then supervisor override → **Approved** |
| S-07 | Second request same date while manual review pending | **Blocked** at submit (duplicate) |
| S-08 | Date before **2026-06-28** | Rejected |
| S-09 | On-duty replacement for Squad A day shift bump on a **working day** | Eligible same-squad officer on allowed shift, scheduled working |

| S-10 | Squad A day shift (06:00) requests off on **squad off day** | → **Pending Manual Review** (no on-duty replacement; **0** overrides) |
| S-11 | Two Squad A officers swap on a working day (**2026-06-28**) | Approve swap → **2** `Shift Swap` overrides on that date |

Run all scenarios: `python dev.py scenarios`

**Department notes:**

```
Command staff (Chief, Lieutenant): Monday–Friday in base schedule; manual edits/overrides allowed.
Patrol squads follow the 14-day A/B rotation above.
```

---

## 11. Open product backlog (from project plan)

Priority for future work — **reorder as needed:**

1. [x] Cascading bump / covered-shift modeling
2. [x] Notifications tab + create on approve/reject
3. [x] Shift swap UI + approval + schedule effect
4. [x] Payroll type rules (Comp, Sick, Unpaid, etc.)
5. [x] PDF export (schedule / payroll)
6. [x] Logo/branding in app header
7. [x] In-app database backup (+ weekly auto-backup on launch)
8. [x] User management UI + forced password change on first login
9. [x] Officer iCal schedule export

---

## Document history

| Date | Change |
|------|--------|
| 2026-06-29 | Initial draft exported from codebase for department review |

**Reviewed by:** _________________ **Date:** _________
