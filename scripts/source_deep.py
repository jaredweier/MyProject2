"""
Source-deep dig — how real scheduling/UI systems are *written*, not marketed.

Reads public code patterns (OR-Tools, Timefold, Staffjoy architecture notes,
NiceGUI AG Grid) and compares to Chronos modules. Machine-local, free.

    python dev.py source-deep
    python dev.py source-deep chronos
    python dev.py source-deep compare
    python dev.py source-deep lessons
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Public source architectures (deposited from reading real code / READMEs)
EXTERNAL_SOURCES: List[Dict[str, Any]] = [
    {
        "id": "ortools-shift-scheduling-sat",
        "kind": "code",
        "lang": "python",
        "url": "https://github.com/google/or-tools/blob/stable/examples/python/shift_scheduling_sat.py",
        "how_written": [
            "Boolean decision vars work[e,s,d] for employee × shift × day",
            "Hard: exactly_one shift per employee per day",
            "Soft sequence: negated_bounded_span + penalty literals for under/over run lengths",
            "Soft sum: IntVar excess for weekly min/max with linear penalties",
            "Transitions: forbid night→morning (cost 0) or penalize afternoon→night",
            "Cover: min demand hard sum; excess staffing linear penalty by band",
            "Objective = sum(bool_penalties*coeff) + sum(int_excess*coeff); minimize",
            "Solve prints each violated penalty name — explainability pattern",
        ],
        "chronos_map": [
            "logic/cp_sat_bridge.py: x[o,d,b] bools, coverage minima, minimize sum",
            "logic/coverage_optimizer.py: beam search + weighted score (not full CP)",
            "validators rest/night: hard filters before scoring (like hard constraints)",
        ],
    },
    {
        "id": "timefold-employee-scheduling-java",
        "kind": "code",
        "lang": "java",
        "url": "https://github.com/TimefoldAI/timefold-quickstarts/blob/stable/java/employee-scheduling/src/main/java/org/acme/employeescheduling/solver/EmployeeSchedulingConstraintProvider.java",
        "how_written": [
            "ConstraintProvider.defineConstraints() returns ordered Constraint[]",
            "HARD: requiredSkill, noOverlappingShifts, ≥10h between shifts, oneShiftPerDay, unavailableEmployee",
            "SOFT: undesiredDay (penalize), desiredDay (reward), balanceEmployeeShiftAssignments (loadBalance unfairness)",
            "Score type HardSoftBigDecimalScore — hard must be 0, soft optimizes",
            "Planning entity = Shift with employee as planning variable",
            "Skills on Employee; requiredSkill on Shift — cert gate pattern",
        ],
        "chronos_map": [
            "Hard filters in list_scored_replacements (rest, consecutive, cert, squad, cover rules)",
            "Soft multi-objective: w_junior*rank + w_spare + w_same_start + depth_bonus",
            "plan_explain.explain_coverage_plans — supervisor score narrative",
            "certifications.officer_meets_shift_cert_requirements ≈ requiredSkill",
        ],
    },
    {
        "id": "staffjoy-suite-chomp-mobius",
        "kind": "architecture",
        "lang": "python/flask + microservices",
        "url": "https://github.com/Staffjoy/suite",
        "how_written": [
            "Split pipeline: Chomp = shift creation from forecast; Mobius = assignment under constraints",
            "Flask app + MySQL + Redis; cron hits /api/v2/internal/cron every 60s",
            "HTTP basic API tokens; workers claim shifts / clock-in",
            "SMS via Twilio; email Mandrill — notification channels as services",
            "YAPF/PEP8 fmt gate; Alembic-style migrations",
            "Config via env (SECRET_KEY, SQLALCHEMY_DATABASE_URI) — never hardcode secrets",
        ],
        "chronos_map": [
            "Chronos: logic/* generation (rotation) vs coverage_optimizer assignment",
            "open-shift-digest + create_notification ≈ lightweight notify path",
            "SQLite single-process vs Suite multi-service — stay modular for future split",
            "dev.py verify gates ≈ Suite make fmt / tests",
        ],
    },
    {
        "id": "nicegui-aggrid",
        "kind": "ui-code",
        "lang": "python",
        "url": "https://nicegui.io/documentation/aggrid",
        "how_written": [
            "ui.aggrid(options dict) with columnDefs + rowData",
            "floatingFilter + agTextColumnFilter / agNumberColumnFilter",
            "theme quartz|balham|material|alpine; dark follows page",
            "run_grid_method / get_selected_rows / update options then grid.update()",
            "cellClassRules for conditional severity styling",
            "Prefer transaction applyTransaction for edits without full rebuild",
        ],
        "chronos_map": [
            "gui/tables.py aggrid_from_dicts — quartz, floating filters, CSV export",
            "severity_strip for NOC alert chips outside grid",
        ],
    },
    {
        "id": "staffjoy-autoscheduler-julia",
        "kind": "code-history",
        "lang": "julia",
        "url": "https://github.com/Staffjoy/autoscheduler",
        "how_written": [
            "Combined shift creation + assignment (later split Chomp/Mobius)",
            "MIP (JuMP) + dynamic programming heuristics mixed",
            "Week model maximizes lift = availability / demand hours",
            "Lesson: rewrite when combined solver becomes unmaintainable — modularize",
        ],
        "chronos_map": [
            "Rust scheduler_core for cycle math; Python beam for multi-plan search",
            "Do not re-derive bump tables in UI",
        ],
    },
    {
        "id": "ukg-telestaff",
        "kind": "product-architecture",
        "lang": "saas",
        "url": "https://www.ukg.com/products/ukg-telestaff",
        "how_written": [
            "Rules engine applies union/HR/fatigue policies to build rosters",
            "Static schedule + rotations + daily assignments in one system of record",
            "Min-staffing roster alarms (hard coverage signals)",
            "Vacancy fill ranks by fatigue hours, certs, availability, policy",
            "Notify via text/email/voice — multi-channel, not only in-app",
            "Bidding for location/shift/days-off as first-class module",
            "Extra duty events: plan → staff → track → invoice (cost recovery)",
            "Self-service trades/TO with auto-approve when rules pass",
            "Integrations: CAD, RMS, payroll; reporting via BIRT",
            "Segment editions: LE, Fire/EMS, Corrections",
        ],
        "chronos_map": [
            "Min staffing + night min + open shifts + cert gates exist",
            "Bidding + digests partial; voice/SMS and extra-duty invoicing MISS",
            "plan_explain + bulk auto-OK leave ≈ rule-aware self-service",
        ],
    },
    {
        "id": "neogov-time-attendance-payroll",
        "kind": "product-payroll",
        "lang": "saas",
        "url": "https://www.neogov.com/products/time-and-attendance-software",
        "how_written": [
            "Work rules engine: OT, meal breaks, shift differentials auto-applied",
            "FLSA 7(k) work periods + blended rate handling",
            "Employee button: convert OT hours → comp time when eligible",
            "Leave donations as public-sector leave bank feature",
            "Lookback OT calculated in payroll when cycle ≠ pay period",
            "Approved hours flow to payroll without re-key",
            "Geofenced clock-in optional",
        ],
        "chronos_map": [
            "get_flsa_settings + pay codes + banks + lock period",
            "Cash vs comp via entry types; no leave-donation ledger yet",
            "prefill_timecard_from_schedule ≈ schedule→timesheet",
        ],
    },
    {
        "id": "netchex-le-payroll",
        "kind": "product-payroll",
        "lang": "saas",
        "url": "https://netchex.com/blog/payroll-software-sheriffs-offices-law-enforcement/",
        "how_written": [
            "Dual OT calculation: sworn 7(k) + civilian 40h same payroll run",
            "Comp 1.5x with 480h public-safety / 240h civilian caps",
            "Specialty assignment pay feeds regular rate for OT",
            "Off-duty detail tracking separate from duty roster",
            "Shift differentials blended into FLSA regular rate",
        ],
        "chronos_map": [
            "Single FLSA path today — dual workforce is product gap",
            "Comp 480h meter exists; civilian 240h cap not dual-mode",
            "Extra duty / Callback pay codes exist; detail billing thin",
        ],
    },
    {
        "id": "eso-scheduling-fire-ems",
        "kind": "product-architecture",
        "lang": "saas",
        "url": "https://www.eso.com/fire/",
        "how_written": [
            "Scheduling nested in fire/EMS records platform (not standalone-only)",
            "Unit/station/assignment roster dimensions",
            "Cert + immunization readiness gates next to schedule",
            "Open shift bid + call-out + swaps",
            "Data sync to RMS/ePCR ecosystems",
        ],
        "chronos_map": [
            "Cert gates exist; immunizations not modeled",
            "Squad/shift bands ≈ station posts (single precinct scope)",
        ],
    },
]


def _scan_chronos_modules() -> Dict[str, Any]:
    """AST-level scan of how Chronos scheduling code is structured."""
    targets = {
        "coverage_optimizer": ROOT / "logic" / "coverage_optimizer.py",
        "cp_sat_bridge": ROOT / "logic" / "cp_sat_bridge.py",
        "plan_explain": ROOT / "logic" / "plan_explain.py",
        "scheduling": ROOT / "logic" / "scheduling.py",
        "validators": ROOT / "validators.py",
        "tables": ROOT / "gui" / "tables.py",
    }
    out: Dict[str, Any] = {}
    for name, path in targets.items():
        if not path.is_file():
            out[name] = {"exists": False}
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            out[name] = {"exists": True, "error": str(exc)}
            continue
        funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
        out[name] = {
            "exists": True,
            "lines": sum(1 for _ in path.open(encoding="utf-8")),
            "functions": funcs[:40],
            "classes": classes,
            "path": str(path.relative_to(ROOT)),
        }
    return out


def cmd_show() -> int:
    print("Source-deep — how scheduling/UI systems are written")
    print("=" * 72)
    print("commands: show | sources | chronos | compare | lessons")
    print()
    print("External patterns catalogued:", len(EXTERNAL_SOURCES))
    for s in EXTERNAL_SOURCES:
        print(f"  [{s['id']}] {s['kind']} · {s.get('lang')}")
    print()
    print("Also: fr-domain dig · math-domain explore · ui-domain explore")
    return 0


def cmd_sources() -> int:
    print("EXTERNAL SOURCE IMPLEMENTATION NOTES")
    print("=" * 72)
    for s in EXTERNAL_SOURCES:
        print(f"\n## {s['id']}")
        print(f"   {s.get('url')}")
        print("   How written:")
        for line in s.get("how_written") or []:
            print(f"     • {line}")
        print("   Chronos map:")
        for line in s.get("chronos_map") or []:
            print(f"     → {line}")
    return 0


def cmd_chronos() -> int:
    print("CHRONOS LOCAL CODE STRUCTURE (AST scan)")
    print("=" * 72)
    scan = _scan_chronos_modules()
    for name, info in scan.items():
        if not info.get("exists"):
            print(f"\n[{name}] missing")
            continue
        print(f"\n[{name}] {info.get('path')} · ~{info.get('lines')} lines")
        if info.get("classes"):
            print("  classes:", ", ".join(info["classes"]))
        funcs = info.get("functions") or []
        print("  funcs:", ", ".join(funcs[:15]) + ("…" if len(funcs) > 15 else ""))
    print("\nPattern: validators/hard filters → coverage_optimizer scores → plan_explain text")
    print("         optional cp_sat_bridge for multi-day feasibility")
    print("         gui/tables for dense enterprise grids")
    return 0


def cmd_compare() -> int:
    print("COMPARE: external writing style vs Chronos")
    print("=" * 72)
    rows = [
        ("Decision vars", "OR-Tools work[e,s,d]", "CP-SAT x[o,d,b]; beam chains not full roster MIP"),
        ("Hard constraints", "Timefold HARD score 0", "filters in list_scored_replacements + validators"),
        ("Soft objective", "penalties + rewards + loadBalance", "w_junior/w_spare/w_same/w_shallow weights"),
        ("Explainability", "OR-Tools print each penalty", "plan_explain + leave Plans dialog"),
        ("Pipeline split", "Staffjoy Chomp then Mobius", "rotation/rust generate; optimizer assigns bumps"),
        ("UI tables", "NiceGUI AG Grid options API", "gui/tables.aggrid_from_dicts"),
        ("Notify", "Twilio/SMS services", "create_notification + open-shift-digest"),
    ]
    for theme, external, chronos in rows:
        print(f"\n{theme}")
        print(f"  external: {external}")
        print(f"  chronos:  {chronos}")
    print("\nImplement next when gap hurts product:")
    print("  • Richer score breakdown in plan_explain (component weights)")
    print("  • Soft transition penalties (night→day) if CBA requires")
    print("  • Fairness load-balance term on OT equity ledger")
    return 0


def cmd_lessons() -> int:
    print("IMPLEMENTATION LESSONS (from reading real sources)")
    print("=" * 72)
    lessons = [
        "Separate hard feasibility from soft quality — never mix into one boolean.",
        "Name every soft penalty (OR-Tools style) so supervisors can audit scores.",
        "Keep skill/cert checks as hard filters before soft ranking (Timefold requiredSkill).",
        "Split forecast→shifts from worker→shift assignment when complexity grows (Staffjoy).",
        "UI: grids are options dicts + refresh; don't rebuild business rules in the browser.",
        "Print/export solver stats and violated constraints after every optimize run.",
        "Config weights (w_junior…) must be department-tunable — CBAs differ.",
        "Cron/jobs for digests; don't block request path on mass notify.",
    ]
    for i, L in enumerate(lessons, 1):
        print(f"  {i}. {L}")
    print("\nDeposit: python dev.py fr-domain learn / math-domain learn / ui-domain learn")
    return 0


def run_source_deep(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Deep source implementation dig")
    p.add_argument(
        "command",
        nargs="?",
        default="show",
        help="show|sources|chronos|compare|lessons",
    )
    args = p.parse_args(list(argv) if argv is not None else None)
    cmd = (args.command or "show").replace("_", "-")
    if cmd == "show":
        return cmd_show()
    if cmd in ("sources", "external"):
        return cmd_sources()
    if cmd == "chronos":
        return cmd_chronos()
    if cmd == "compare":
        return cmd_compare()
    if cmd in ("lessons", "implement"):
        return cmd_lessons()
    print(f"Unknown {cmd}")
    return cmd_show()


if __name__ == "__main__":
    raise SystemExit(run_source_deep())
