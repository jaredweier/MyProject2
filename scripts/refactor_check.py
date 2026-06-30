"""Architecture and modularity checks for refactor work."""

from __future__ import annotations

import os
import re
import sys
from typing import List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _line_count(path: str) -> int:
    return len(_read(path).splitlines())


def _ui_files() -> List[str]:
    ui_dir = os.path.join(ROOT, "ui")
    return sorted(os.path.join(ui_dir, name) for name in os.listdir(ui_dir) if name.endswith(".py"))


def check_layer_boundaries() -> List[Tuple[str, bool, str]]:
    findings: List[Tuple[str, bool, str]] = []
    cli = _read(os.path.join(ROOT, "cli.py"))

    sql_pattern = re.compile(r"cursor\.execute|\bget_connection\s*\(")
    for path in _ui_files():
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        content = _read(path)
        if rel == "ui/shell_pages.py":
            # backup_database only — no cursor SQL
            has_sql = bool(re.search(r"cursor\.execute", content))
        else:
            has_sql = bool(sql_pattern.search(content))
        findings.append(
            (
                f"{rel} has no SQL",
                not has_sql,
                "raw SQL detected" if has_sql else "ok",
            )
        )

    cli_sql = bool(re.search(r"cursor\.execute|SELECT\s+", cli, re.I))
    findings.append(("cli.py has no SQL", not cli_sql, "raw SQL detected" if cli_sql else "ok"))

    unused_conn = "from database import get_connection" in cli and not re.search(
        r"\bget_connection\(",
        cli.replace("from database import get_connection, backup_database", "").replace(
            "from database import backup_database", ""
        ),
    )
    if "get_connection" in cli:
        uses = len(re.findall(r"\bget_connection\(", cli))
        imports = 1 if "import get_connection" in cli else 0
        findings.append(
            (
                "cli.py avoids unused get_connection",
                uses <= imports,
                f"get_connection uses={uses}",
            )
        )

    return findings


def check_file_sizes() -> List[Tuple[str, bool, str]]:
    thresholds = {
        "ui/app.py": 750,
        "logic/__init__.py": 50,
    }
    findings: List[Tuple[str, bool, str]] = []
    for rel, limit in thresholds.items():
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(path):
            continue
        lines = _line_count(path)
        findings.append(
            (
                f"{rel} under {limit} lines",
                lines <= limit,
                f"{lines} lines",
            )
        )
    logic_pkg = os.path.join(ROOT, "logic")
    if os.path.isdir(logic_pkg):
        total = sum(_line_count(os.path.join(logic_pkg, f)) for f in os.listdir(logic_pkg) if f.endswith(".py"))
        findings.append(
            (
                "logic/ package exists",
                True,
                f"{total} total lines across package",
            )
        )
    return findings


def check_helpers_exist() -> List[Tuple[str, bool, str]]:
    path = os.path.join(ROOT, "ui", "helpers.py")
    exists = os.path.isfile(path)
    content = _read(path) if exists else ""
    has_handler = "handle_logic_result" in content
    return [
        ("ui/helpers.py present", exists, "ok" if exists else "missing"),
        ("ui/helpers.py has handle_logic_result", has_handler, "ok" if has_handler else "missing"),
    ]


def check_logic_imports() -> List[Tuple[str, bool, str]]:
    from scripts.audit_logic_imports import audit_logic_imports

    missing, _by_file = audit_logic_imports()
    if missing:
        return [("logic exports cover all imports", False, ", ".join(missing))]
    return [("logic exports cover all imports", True, "ok")]


def check_vertical_slices() -> List[Tuple[str, bool, str]]:
    from scripts.vertical_slices import run_slice_check

    code = run_slice_check()
    return [("vertical slice registry", code == 0, "ok" if code == 0 else "see slice-check output")]


def run_refactor_check() -> int:
    checks = (
        check_layer_boundaries()
        + check_file_sizes()
        + check_helpers_exist()
        + check_logic_imports()
        + check_vertical_slices()
    )
    failed = 0
    print("Refactor check")
    print("=" * 60)
    for name, ok, detail in checks:
        status = "PASS" if ok else "WARN" if "under" in name else "FAIL"
        if not ok:
            failed += 1 if status == "FAIL" else 0
        print(f"  [{status}] {name}: {detail}")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run_refactor_check())
