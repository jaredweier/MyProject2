"""Ruff lint and format gate — free OSS alternative to agent code review."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ruff_cmd() -> list[str] | None:
    exe = shutil.which("ruff")
    if exe:
        return [exe]
    try:
        import ruff  # noqa: F401

        return [sys.executable, "-m", "ruff"]
    except ImportError:
        return None


def run_lint(*, fix: bool = False, format_code: bool = False) -> int:
    os.chdir(ROOT)
    cmd = _ruff_cmd()
    if cmd is None:
        print("lint: ruff not installed")
        print("  pip install -r requirements-dev.txt")
        return 1

    print("Dodgeville PD Scheduler — lint (ruff)")
    print("=" * 60)

    steps: list[tuple[str, list[str]]] = []
    check_args = ["check", "."]
    if fix:
        check_args.append("--fix")
    steps.append(("ruff check", cmd + check_args))
    if format_code:
        steps.append(("ruff format", cmd + ["format", "."]))

    failed: list[str] = []
    for label, argv in steps:
        print(f"\n>>> {label}", flush=True)
        result = subprocess.run(argv, cwd=ROOT)
        if result.returncode != 0:
            failed.append(label)

    print("\n" + "=" * 60)
    if failed:
        print(f"lint: FAILED — {', '.join(failed)}")
        print("  Fix manually or: python dev.py lint --fix")
        return 1
    print("lint: ALL PASSED")
    return 0


if __name__ == "__main__":
    fix = "--fix" in sys.argv
    fmt = "--format" in sys.argv
    raise SystemExit(run_lint(fix=fix, format_code=fmt))
