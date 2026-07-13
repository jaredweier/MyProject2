"""Extract bump-chain helpers from logic/scheduling.py → logic/scheduling_bump.py.

Idempotent: if names already live only as re-exports, exit cleanly.
Keeps public surface on logic.scheduling via re-export (same as scheduling_sim).
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "logic" / "scheduling.py"
OUT = ROOT / "logic" / "scheduling_bump.py"

# Order preserved for readability
NAMES = (
    "_chain_excluded_officer_ids",
    "_bump_assignment_counts_for_date",
    "_bump_capacity_exhausted",
    "count_remaining_on_shift_band",
    "_shift_retains_coverage_after_bump",
    "_night_minimum_uncovered_failure",
    "find_replacement_officer",
    "_bump_suggestion_from_rust",
    "suggest_bump_chain",
    "_minimum_rest_manual_failure",
    "_consecutive_days_manual_failure",
    "_suggest_bump_chain_python",
    "plan_bump_chain",
    "format_bump_suggestion",
    "validate_bump_feasibility",
)

HEADER = '''"""Bump chain planning and replacement pick.

Extracted from ``logic.scheduling`` so rotation/matrix stay navigable.
Public names re-exported from ``logic.scheduling`` and ``import logic``.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Set, Tuple

import config
from config import is_high_risk_night
from database import get_connection
from logic import rust_bridge
from logic.officers import get_officer_by_id, get_officers_by_seniority
from models import BumpChainStep, BumpChainSuggestion, BumpSimulationResult
from validators import applies_night_minimum, night_minimum_violation, parse_date


def _scheduling():
    """Lazy import of parent module to avoid circular import at load time."""
    import logic.scheduling as s

    return s


'''

REEXPORT = """
# Bump chain (extracted)
from logic.scheduling_bump import (  # noqa: E402
    count_remaining_on_shift_band,
    find_replacement_officer,
    suggest_bump_chain,
    plan_bump_chain,
    format_bump_suggestion,
    validate_bump_feasibility,
)
"""


def _rewrite_body(chunk: str) -> str:
    """Rewrite private helper calls to go through _scheduling() where defined in parent."""
    # Helpers that remain in scheduling.py
    parent_helpers = (
        "_get_generated_schedule_day_context",
        "_officer_schedule_working",
        "_normalize_shift_band",
        "_officer_scheduled_shift_start",
        "_replacement_shift_start_for_rules",
        "count_officers_on_shift_on_date",
        "compute_minimum_rest_gap",
        "officer_meets_minimum_rest",
        "describe_minimum_rest_violation",
        "get_officer_effective_shift_band",
        "_shift_bounds",
        "_shift_end_for_start",
        "get_active_bump_rules_by_start",  # actually staffing
    )
    # Only rewrite bare calls that are parent helpers, not our local defs
    # Use S. = _scheduling() at start of functions that need many — simpler: replace known names
    replacements = {
        "_get_generated_schedule_day_context(": "_scheduling()._get_generated_schedule_day_context(",
        "_officer_schedule_working(": "_scheduling()._officer_schedule_working(",
        "_normalize_shift_band(": "_scheduling()._normalize_shift_band(",
        "_officer_scheduled_shift_start(": "_scheduling()._officer_scheduled_shift_start(",
        "_replacement_shift_start_for_rules(": "_scheduling()._replacement_shift_start_for_rules(",
        "count_officers_on_shift_on_date(": "_scheduling().count_officers_on_shift_on_date(",
        "compute_minimum_rest_gap(": "_scheduling().compute_minimum_rest_gap(",
        "officer_meets_minimum_rest(": "_scheduling().officer_meets_minimum_rest(",
        "describe_minimum_rest_violation(": "_scheduling().describe_minimum_rest_violation(",
        "get_officer_effective_shift_band(": "_scheduling().get_officer_effective_shift_band(",
        "_shift_bounds(": "_scheduling()._shift_bounds(",
        "_shift_end_for_start(": "_scheduling()._shift_end_for_start(",
    }
    out = chunk
    for a, b in replacements.items():
        out = out.replace(a, b)
    return out


def main() -> None:
    src = SRC.read_text(encoding="utf-8")
    if "from logic.scheduling_bump import" in src and OUT.exists():
        print("already extracted — scheduling_bump present and re-exported")
        return

    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    ranges: dict[str, tuple[int, int]] = {}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in NAMES:
            ranges[n.name] = (n.lineno, n.end_lineno or n.lineno)

    missing = [n for n in NAMES if n not in ranges]
    if missing:
        raise SystemExit(f"missing in scheduling.py: {missing}")

    body_parts = []
    for name in NAMES:
        s, e = ranges[name]
        chunk = "".join(lines[s - 1 : e])
        body_parts.append(_rewrite_body(chunk))

    OUT.write_text(HEADER + "\n\n".join(body_parts) + "\n", encoding="utf-8")

    ordered = sorted(ranges.values(), key=lambda t: t[0], reverse=True)
    new_lines = lines[:]
    for s, e in ordered:
        del new_lines[s - 1 : e]

    text = "".join(new_lines).rstrip() + "\n"
    if "from logic.scheduling_bump import" not in text:
        text = text + "\n" + REEXPORT + "\n"
    SRC.write_text(text, encoding="utf-8")

    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"scheduling.py lines ~{text.count(chr(10)) + 1}")
    print(f"scheduling_bump.py lines ~{OUT.read_text(encoding='utf-8').count(chr(10)) + 1}")


if __name__ == "__main__":
    main()
