# Three brains — allowed edges + contract

**Product model:** schedule **generator**, schedule **optimizer**, **payroll**.
Shared **facts** OK. **Math/rules** stay in-home.

Last update: 2026-07-16.

Boundary regression: `tests/test_three_brains_boundary.py`.

---

## 1. Ownership (modules)

| Brain | Owns (math + rules) | Notes |
|-------|---------------------|--------|
| **Generator** | `scheduling.py`, `scheduling_matrix.py`, `rotation_config.py`, `rotation_patterns.py`, `rotation_preview.py`, `shift_assignment.py`, `rust_bridge.py` / `rust_fallback.py`, `snapshots.py`, `staffing_config.py` | “Who works when” from rotation + overrides |
| **Optimizer** | `coverage_optimizer.py` (public bump/coverage), `bump_optimizer.py` (bump impl), `staffing_optimizer.py`, `scheduling_sim.py`, `optimized_schedule_apply.py`, `ot_fill.py`, `cp_sat_bridge.py`, `bump_off_duty.py` | Coverage plans, cascades, multi-plan search, staffing scenarios |
| **Payroll** | `logic/payroll/*` (`period`, `timecard`, `entries`, `pay_codes`, `banks`) | Hours → money, banks, locks, pay codes |
| **Shared kernel** | `config`, `models`, `database`, `validators`, `officers`, `operations`, `users`, `permissions` | No domain math |

**Glue (not a 4th brain):** `requests.py`, `bidding.py`, `exports.py`, `analytics.py`, `labor_compliance.py`, `extra_duty.py` — call brains; no OT/pay or coverage scoring ownership.

### Import homes (current)

| Need | Import from |
|------|-------------|
| Day status / matrix / rest / cycle | `logic.scheduling` or `logic.scheduling_matrix` |
| Bump / coverage plans | `logic.coverage_optimizer` (impl: `logic.bump_optimizer`) |
| Sim / staffing search | `logic.scheduling_sim` |
| Timecard / pay | `logic.payroll` |
| Glue tooling | `scripts/logic_resolve.logic_has` finds symbols on brain modules |

`logic.scheduling` **must not** re-export optimizer symbols.
`import logic` **must not** re-export optimizer symbols (use brain modules).
`logic.scheduling_bump` **removed**.

---

## 2. Allowed edges

Direction = **caller → callee**.

### Shared facts (any brain may read)

| Fact | Preferred source |
|------|------------------|
| Roster / seniority / home band | `officers`, `staffing_config` |
| Rotation pattern / cycle / base date | `rotation_config`, `rotation_patterns` |
| Day status / “working that day?” | Generator: `get_officer_day_status`, `batch_officer_day_status`, `build_schedule_matrix`, `is_officer_working_on_day`, cycle windows |
| Snapshots | `snapshots` (read) |
| Dept knobs | `config` + `operations.get_department_setting` |
| Dates | `validators` |

### Generator → others

| May call | Why |
|----------|-----|
| Shared kernel | Load/write roster, settings, snapshots |
| **Optimizer** | Only when orchestrating “suggest best coverage” from a generator-adjacent flow — prefer leave/requests glue instead |
| **Payroll** | **Forbidden** |

### Optimizer → others

| May call | Why |
|----------|-----|
| Shared kernel | Officers, settings |
| **Generator public** day/band/rest facts | Inputs only |
| **Payroll** | **Forbidden** for pay math. Implement-date calendar uses `config.PAY_PERIOD_*` only |
| Apply path | Settings/defaults + trigger generator snapshot regenerate |

### Payroll → others

| May call | Why |
|----------|-----|
| Shared kernel | Officers, settings, audit |
| **Generator public** worked/hours/cycle facts | Timecard prefill |
| **Optimizer** | **Forbidden** |
| Snapshots (read) | Optional assigned bands |

### Hard bans

1. No payroll ↔ optimizer pay math.
2. No optimizer import of `logic.payroll.*`.
3. No generator multi-plan scoring / staffing scenario search.
4. No new `from logic.scheduling import _private_*` outside generator+optimizer (prefer public names).
5. Multi-block / multi-plan coverage search lives in **optimizer** only.

---

## 3. Dependency sketch

```
          officers / config / operations / validators
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   [GENERATOR]  ──facts──►  [OPTIMIZER]
   rotation/matrix          scores/plans
   snapshots write ◄──apply defaults──┘
         │
         │ day status / shift hours
         ▼
      [PAYROLL]
```

---

## 4. Cleanup completed (2026-07-16)

| Item | Status |
|------|--------|
| Generator public facts (+ `_` aliases) | Done |
| Payroll → `scheduling_matrix` public facts | Done |
| Optimizer uses public generator facts | Done |
| Bump public via `coverage_optimizer` | Done |
| `scheduling` no longer re-exports bump/sim | Done |
| `bump_optimizer.py` canonical; `scheduling_bump` **removed** | Done |
| Production + tests/audit/scripts import optimizer homes | Done |
| `recommend_implement_dates` config-only | Done |
| Slice `brain:` tags | Done |
| Boundary unit tests | Done |
| `import logic` no longer re-exports optimizer | Done |
| `scripts/logic_resolve` for feature-map / slice-check | Done |
| Boundary tests in readiness (verify --tier fast) | Done |

---

## 5. Agent rule

```
if change is rotation / day status / matrix / snapshots seed → GENERATOR
if change is score / cascade / multi-plan / staffing search / OT fill order → OPTIMIZER
if change is rates / OT pay / holiday mult / banks / period lock / timecard $ → PAYROLL
if need other brain → call public fact API only; do not copy formulas
```

Prove in owning brain’s tests; don’t “fix” payroll by tweaking optimizer scores.
