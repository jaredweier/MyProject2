"""
Property-style fuzz for scheduling invariants — free local CPU.

Uses Hypothesis if installed; otherwise a pure-Python random battery.
Catches edge cases unit examples miss (cycle wrap, rest gaps, date parse).

    python dev.py fuzz-scheduling
    python dev.py fuzz-scheduling --examples 200
"""

from __future__ import annotations

import os
import random
import sys
from datetime import date, timedelta
from typing import List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _hypothesis_available() -> bool:
    try:
        import hypothesis  # noqa: F401

        return True
    except ImportError:
        return False


def _pure_fuzz(n: int, seed: int = 0) -> List[Tuple[str, bool, str]]:
    import logic
    from config import ROTATION_BASE_DATE, ROTATION_CYCLE_LENGTH
    from validators import format_date, parse_date, validate_minimum_rest_gap

    rng = random.Random(seed)
    results = []

    # Cycle day in 1..cycle_length always
    ok_all = True
    detail = ""
    for _ in range(n):
        delta = rng.randint(0, 5000)
        d = ROTATION_BASE_DATE + timedelta(days=delta)
        cd = logic.get_cycle_day(d)
        if not (1 <= cd <= ROTATION_CYCLE_LENGTH):
            ok_all = False
            detail = f"bad cycle day {cd} for {d}"
            break
        # wrap property
        cd2 = logic.get_cycle_day(d + timedelta(days=ROTATION_CYCLE_LENGTH))
        if cd2 != cd:
            ok_all = False
            detail = f"wrap fail {d} cd={cd} +len -> {cd2}"
            break
    results.append(("fuzz-cycle-range-wrap", ok_all, detail or f"n={n}"))

    # parse_date / format_date round-trip on ISO
    ok_rt = True
    detail = ""
    for _ in range(n):
        y = rng.randint(2026, 2030)
        m = rng.randint(1, 12)
        day = rng.randint(1, 28)
        iso = f"{y:04d}-{m:02d}-{day:02d}"
        parsed = parse_date(iso)
        if parsed is None or parsed != date(y, m, day):
            ok_rt = False
            detail = f"ISO parse fail {iso}"
            break
        # US display should re-parse for unambiguous M/D/YYYY
        disp = format_date(parsed)
        # format is M/D/YY — parse back may need full year; skip weak YY roundtrip
        if not disp:
            ok_rt = False
            detail = "empty format"
            break
    results.append(("fuzz-iso-parse-format", ok_rt, detail or f"n={n}"))

    # rest gap monotonic: more hours never worse than fewer
    from config import MIN_REST_HOURS_BETWEEN_SHIFTS as MIN_REST

    ok_rest = True
    detail = ""
    for _ in range(min(n, 100)):
        lo = rng.uniform(0, max(0.1, MIN_REST - 0.05))
        hi = lo + rng.uniform(0.1, 12)
        a = validate_minimum_rest_gap(lo, MIN_REST)
        b = validate_minimum_rest_gap(hi, MIN_REST)
        if a.ok and not b.ok:
            ok_rest = False
            detail = f"monotonic fail lo={lo} hi={hi}"
            break
        if lo < MIN_REST and a.ok:
            ok_rest = False
            detail = f"expected block under {MIN_REST}h got ok for {lo}"
            break
        if hi >= MIN_REST and not b.ok:
            ok_rest = False
            detail = f"expected pass at {hi} >= {MIN_REST}"
            break
    results.append(("fuzz-rest-monotonic", ok_rest, detail or f"n={n} min={MIN_REST}"))

    # squad on duty only A/B
    ok_sq = True
    detail = ""
    for i in range(1, ROTATION_CYCLE_LENGTH + 1):
        sq = logic.get_squad_on_duty(i)
        if sq not in ("A", "B"):
            ok_sq = False
            detail = f"bad squad {sq} day {i}"
            break
    results.append(("fuzz-squad-ab", ok_sq, detail or "ok"))

    return results


def _hypothesis_battery(max_examples: int) -> List[Tuple[str, bool, str]]:
    """Optional Hypothesis-powered properties."""
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    import logic
    from config import ROTATION_BASE_DATE, ROTATION_CYCLE_LENGTH
    from validators import parse_date, validate_minimum_rest_gap

    results: List[Tuple[str, bool, str]] = []
    failures: List[str] = []

    @settings(max_examples=max_examples, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    @given(st.integers(min_value=0, max_value=8000))
    def prop_cycle(delta: int) -> None:
        d = ROTATION_BASE_DATE + timedelta(days=delta)
        cd = logic.get_cycle_day(d)
        assert 1 <= cd <= ROTATION_CYCLE_LENGTH
        assert logic.get_cycle_day(d + timedelta(days=ROTATION_CYCLE_LENGTH)) == cd

    from config import MIN_REST_HOURS_BETWEEN_SHIFTS as MIN_REST

    @settings(max_examples=max_examples, deadline=None)
    @given(st.floats(min_value=0, max_value=24, allow_nan=False, allow_infinity=False))
    def prop_rest(hours: float) -> None:
        r = validate_minimum_rest_gap(hours, MIN_REST)
        if hours < MIN_REST:
            assert not r.ok
        else:
            assert r.ok

    @settings(max_examples=max_examples, deadline=None)
    @given(
        st.integers(min_value=2026, max_value=2035),
        st.integers(min_value=1, max_value=12),
        st.integers(min_value=1, max_value=28),
    )
    def prop_iso(y: int, m: int, day: int) -> None:
        iso = f"{y:04d}-{m:02d}-{day:02d}"
        assert parse_date(iso) == date(y, m, day)

    for name, fn in (
        ("hypothesis-cycle", prop_cycle),
        ("hypothesis-rest", prop_rest),
        ("hypothesis-iso", prop_iso),
    ):
        try:
            fn()
            results.append((name, True, f"examples≤{max_examples}"))
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            results.append((name, False, str(exc)[:200]))

    return results


def run_fuzz_scheduling(*, examples: int = 80, seed: int = 0) -> int:
    print("Dodgeville PD — scheduling fuzz / property battery")
    print("=" * 64)
    cases = _pure_fuzz(examples, seed=seed)
    if _hypothesis_available():
        print("Hypothesis: available — running extra properties")
        cases.extend(_hypothesis_battery(min(examples, 100)))
    else:
        print("Hypothesis: not installed — pure random only (pip install hypothesis)")

    failed = 0
    for name, ok, detail in cases:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"  [{mark}] {name}: {detail}")
    print("=" * 64)
    print(f"fuzz-scheduling: {len(cases) - failed}/{len(cases)} passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--examples", type=int, default=80)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    raise SystemExit(run_fuzz_scheduling(examples=a.examples, seed=a.seed))
