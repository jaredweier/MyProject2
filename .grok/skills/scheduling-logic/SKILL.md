---
name: scheduling-logic
description: >
  Scheduling & math for Chronos — rotation, bumps, optimizers, rest/night,
  Rust bridge, CP-SAT. MAXIMUM capability: any public OR/math source or technique.
  Tool: python dev.py math-domain.
---

# Scheduling logic & mathematics — maximum capability

## Goal

Best scheduling math quality and performance. No solver allowlists.

## Tools

```bash
python dev.py math-domain explore|brainstorm|research-queries|engines|run-checks|learn
python dev.py math-scenarios --with-cpsat
python dev.py fuzz-scheduling
python dev.py scenarios · audit
```

Use arXiv, OR-Tools, MiniZinc, HiGHS, papers, GitHub solvers, textbooks — freely.

## In-repo map

| Area | Where |
|------|--------|
| Rotation / squad | `logic/scheduling.py`, `rust/scheduler_core` |
| Bump / cascade | `coverage_optimizer.py`, bump APIs |
| Validation | `validators.py` |
| CP-SAT what-if | `logic/cp_sat_bridge.py` |
| Payroll math | `logic/payroll.py`, `labor_compliance.py` |

## Freedom

- New optimizers, scoring, Rust/Python splits, optional engines — encouraged if better
- Policy knobs (night min, rest, junior-first) should stay **configurable** and tested
- Deposit: `math-domain learn --url … --as-idea`

## Related

`docs/knowledge/math_logic_sources.json` · `first-responder-wfm` · `payroll-timecard`
