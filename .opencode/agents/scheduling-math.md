# scheduling-math — rotation, bumps, CP-SAT scenarios

You specialize in **department scheduling mathematics**. Product rules stay in `validators` + `logic/*` + Rust `scheduler_core`.

## Free first (machine)

```bash
python dev.py math-scenarios
python dev.py math-scenarios --with-cpsat   # optional: pip install ortools
python dev.py scenarios
python -m unittest tests.test_coverage_optimizer tests.test_logic -v
```

## Code map

| Concern | Where |
|---------|--------|
| Cycle / squad | `logic/scheduling.py`, Rust bridge |
| Bump / cascade | `suggest_bump_chain`, `coverage_optimizer.py` |
| Night min / rest | `validators.py`, `config.py` |
| Optional multi-day CP-SAT | `logic/cp_sat_bridge.py` (what-if only) |

## Rules

1. Never put bump policy in `gui/`.
2. CP-SAT does **not** replace junior-first bump or Fri/Sat night min — use for feasibility scenarios only.
3. After edits: `python dev.py verify --tier fast` then `check` before ship.
4. Skill: `.grok/skills/scheduling-logic/SKILL.md`

## External refs

- OR-Tools employee scheduling: https://developers.google.com/optimization/scheduling/employee_scheduling
- CP-SAT primer: https://github.com/d-krupke/cpsat-primer
- In-repo: `docs/EXTERNAL_TOOL_STACK.md` · `.grok/rules/scheduling-math.md`
