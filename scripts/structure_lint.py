"""Free architecture structure lint — layering, monoliths, dual analytics."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]

# Soft size targets (lines) — warn, don't fail by default
# After 2026-07 package splits: payroll + finance are packages; soft max applies
# to largest leaf modules and remaining monoliths.
MONOLITH_WARN = {
    "ui/payroll_pages.py": 2200,
    "cli.py": 1600,
    "logic/scheduling.py": 1400,
    "logic/payroll/timecard.py": 1100,
    "logic/requests.py": 1300,
    "validators.py": 1100,
    "gui/pages/finance/timecards.py": 500,
    "gui/pages/finance/payroll_page.py": 450,
}


def _py_files(folder: str) -> List[Path]:
    base = ROOT / folder
    if not base.is_dir():
        return []
    return [p for p in base.rglob("*.py") if "__pycache__" not in p.parts]


def check_ui_no_sql() -> List[str]:
    """Flag real SQL/driver use in UI — not English words like update/select."""
    issues = []
    # Real smells only (avoid matching "Update password" / "select officer")
    # Avoid English UI copy ("Select from dropdown"). Require SQL-ish tokens.
    pat = re.compile(
        r"(cursor\.execute|sqlite3\.|from database import get_connection|"
        r"\bimport sqlite3\b|"
        r"INSERT\s+INTO\s+[a-z_][a-z0-9_]*|"
        r"DELETE\s+FROM\s+[a-z_][a-z0-9_]*|"
        r"UPDATE\s+[a-z_][a-z0-9_]*\s+SET\b|"
        r"\bJOIN\s+[a-z_][a-z0-9_]*\s+ON\b)",
        re.I,
    )
    for p in _py_files("ui"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        if pat.search(text):
            issues.append(f"UI SQL smell: {p.relative_to(ROOT).as_posix()}")
    return issues


def check_ui_import_logic_package() -> List[str]:
    """UI should import logic package, not deep database paths for business rules."""
    issues = []
    for p in _py_files("ui"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"from database import get_connection|import sqlite3", text):
            issues.append(f"UI direct DB: {p.relative_to(ROOT).as_posix()}")
    return issues


def check_cli_thin() -> List[str]:
    """cli.py should not re-implement validators (heuristic)."""
    issues = []
    cli = ROOT / "cli.py"
    if not cli.is_file():
        return issues
    text = cli.read_text(encoding="utf-8", errors="ignore")
    # heuristic: long SQL blocks in cli
    if text.count("cursor.execute") > 5:
        issues.append("cli.py has multiple cursor.execute — keep business SQL in logic/*")
    return issues


def check_monolith_sizes() -> List[str]:
    issues = []
    for rel, limit in MONOLITH_WARN.items():
        p = ROOT / rel
        if not p.is_file():
            continue
        n = sum(1 for _ in p.open(encoding="utf-8", errors="ignore"))
        if n > limit:
            issues.append(f"Monolith size: {rel} is {n} lines (soft max {limit}) — extract mixin/module")
    return issues


def check_analytics_shim() -> List[str]:
    root_a = ROOT / "analytics.py"
    logic_a = ROOT / "logic" / "analytics.py"
    if root_a.is_file() and logic_a.is_file():
        text = root_a.read_text(encoding="utf-8", errors="ignore")
        if "from logic.analytics import" in text or "logic.analytics" in text:
            return []  # intentional re-export
        return ["analytics.py should re-export logic.analytics only"]
    return []


def check_mixin_inheritance() -> List[str]:
    """app.py must compose page mixins — flag empty DodgevilleSchedulerApp bases."""
    app = ROOT / "ui" / "app.py"
    if not app.is_file():
        return []
    tree = ast.parse(app.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "DodgevilleSchedulerApp":
            bases = [ast.unparse(b) if hasattr(ast, "unparse") else getattr(b, "id", "") for b in node.bases]
            if len(bases) < 5:
                return [f"DodgevilleSchedulerApp has few mixins: {bases}"]
    return []


def run_structure_lint(*, strict: bool = False) -> int:
    os.chdir(ROOT)
    print("Dodgeville PD — structure lint (free)")
    print("=" * 56)
    checks: List[Tuple[str, List[str]]] = [
        ("UI no SQL", check_ui_no_sql()),
        ("UI no direct DB", check_ui_import_logic_package()),
        ("CLI thin", check_cli_thin()),
        ("Monolith soft limits", check_monolith_sizes()),
        ("Analytics shim", check_analytics_shim()),
        ("App mixins", check_mixin_inheritance()),
    ]
    hard = 0
    soft = 0
    for label, items in checks:
        if not items:
            print(f"  [ok] {label}")
            continue
        level = "warn" if label.startswith("Monolith") else "fail" if strict else "warn"
        for item in items:
            print(f"  [{level}] {item}")
            if level == "fail":
                hard += 1
            else:
                soft += 1
    print("-" * 56)
    print(f"structure-lint: {hard} hard, {soft} soft")
    if hard:
        return 1
    return 0


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    raise SystemExit(run_structure_lint(strict=args.strict))
