"""Extract simulator/optimizer helpers from logic/scheduling.py."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "logic" / "scheduling.py"
OUT = ROOT / "logic" / "scheduling_sim.py"

NAMES = (
    "run_schedule_simulation",
    "run_staffing_optimizer",
    "preview_best_coverage_plans",
    "get_simulator_defaults_from_roster",
)

HEADER = '''"""Schedule simulation and coverage-plan preview helpers.

Extracted from ``logic.scheduling`` to keep the rotation/bump core smaller.
Public names remain available via ``logic.scheduling`` re-exports.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from validators import parse_date


'''

REEXPORT = """
# Simulator / multi-plan coverage (extracted)
from logic.scheduling_sim import (  # noqa: E402
    run_schedule_simulation,
    run_staffing_optimizer,
    preview_best_coverage_plans,
    get_simulator_defaults_from_roster,
)
"""


def main() -> None:
    src = SRC.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    ranges: dict[str, tuple[int, int]] = {}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in NAMES:
            ranges[n.name] = (n.lineno, n.end_lineno or n.lineno)
    missing = [n for n in NAMES if n not in ranges]
    if missing:
        raise SystemExit(f"missing: {missing}")

    body_parts = []
    for name in NAMES:
        s, e = ranges[name]
        chunk = "".join(lines[s - 1 : e])
        if name == "preview_best_coverage_plans":
            # inject lazy local import for private context helper
            chunk = chunk.replace(
                "ctx = _get_generated_schedule_day_context(parse_date(request_date))",
                "from logic.scheduling import _get_generated_schedule_day_context\n"
                "    ctx = _get_generated_schedule_day_context(parse_date(request_date))",
            )
        body_parts.append(chunk)
    OUT.write_text(HEADER + "\n\n".join(body_parts) + "\n", encoding="utf-8")

    # Remove functions from scheduling.py (highest lineno first)
    ordered = sorted(ranges.values(), key=lambda t: t[0], reverse=True)
    new_lines = lines[:]
    for s, e in ordered:
        del new_lines[s - 1 : e]
        # also drop one trailing blank if present after deletion mess
    text = "".join(new_lines).rstrip() + "\n" + REEXPORT
    SRC.write_text(text, encoding="utf-8")
    print(f"scheduling.py -> {text.count(chr(10)) + 1} lines")
    print(f"scheduling_sim.py -> {(HEADER + chr(10).join(body_parts)).count(chr(10)) + 1} lines")


if __name__ == "__main__":
    main()
