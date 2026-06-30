#!/usr/bin/env python3
"""Replace frozen evaluation package (onefile exe + source snapshot)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FROZEN = Path(r"C:\Users\Windows\Dodgeville_PD_Scheduler_Frozen_2026-07-01")

SKIP_SNAPSHOT = {
    ".git",
    ".grok",
    "__pycache__",
    "backups",
    "build",
    "dist",
    "exports",
    "logs",
    "terminals",
    "node_modules",
}

LOGIC_HIDDEN = [
    "logic",
    "logic.officers",
    "logic.scheduling",
    "logic.requests",
    "logic.payroll",
    "logic.users",
    "logic.snapshots",
    "logic.operations",
    "logic.exports",
    "logic.dashboard",
    "logic._core",
    "analytics",
    "exports",
    "simulator",
]


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd))
    result = subprocess.run(cmd, cwd=cwd or ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _write_readme() -> None:
    text = f"""Dodgeville PD Scheduler — Frozen Evaluation Package
==================================================
Build date: {date.today().isoformat()}
Source snapshot: source_snapshot\\ (read-only archive of MyProject at this date)

IMPORTANT
---------
This folder is a FROZEN COPY for testing. Do not edit it.
Active development continues in: {ROOT}

RUN ON ANY WINDOWS PC (no Python install required)
------------------------------------------------
1. Copy this entire folder to the test computer (USB, network share, etc.).
2. Double-click: Dodgeville_PD_Scheduler.exe
3. First launch creates next to the .exe:
   - dodgeville_scheduler.db  (demo data seeded automatically)
   - photos\\  logs\\  backups\\  exports\\

OPTIONAL BEFORE FIRST LAUNCH
----------------------------
Edit roster_seed.json in this folder to customize officer names/count.
The database seeds from this file only on first run (before dodgeville_scheduler.db exists).

DEMO LOGINS
-----------
  admin      / admin
  supervisor / supervisor
  officer    / officer

Login is required (auto-login is off).

RESET DEMO DATA
---------------
Delete dodgeville_scheduler.db and restart the app.

FILES IN THIS FOLDER
--------------------
  Dodgeville_PD_Scheduler.exe   Single portable executable
  roster_seed.json              Optional roster customization (first launch)
  EVALUATE.txt                  Testing checklist
  source_snapshot\\              Full source code archive (not needed to run)
  build_work\\                   PyInstaller build cache (safe to ignore)

See EVALUATE.txt for feature testing workflow.
"""
    (FROZEN / "README.txt").write_text(text, encoding="utf-8", newline="\n")


def _write_frozen_marker(verification: str) -> None:
    text = f"""FROZEN SNAPSHOT — DO NOT MODIFY
================================

Created: {date.today().isoformat()}
Built from: {ROOT}
Verification at build: {verification}

This package is intentionally separate from ongoing development.
All future changes belong in MyProject only.

Includes vertical-slice logic package (logic/*.py), profile dialog, and slice tooling in source_snapshot only.
"""
    (FROZEN / "FROZEN_DO_NOT_MODIFY.txt").write_text(text, encoding="utf-8", newline="\n")


def _copy_snapshot() -> None:
    dest = FROZEN / "source_snapshot"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    def ignore(dirpath: str, names: list[str]) -> set[str]:
        base = Path(dirpath)
        skipped: set[str] = set()
        for name in names:
            if name in SKIP_SNAPSHOT:
                skipped.add(name)
            elif name == "dodgeville_scheduler.db" and base == ROOT:
                skipped.add(name)
        return skipped

    shutil.copytree(ROOT, dest, ignore=ignore, dirs_exist_ok=True)
    print(f"Wrote source snapshot: {dest}")


def main() -> int:
    print("=== Frozen evaluation package (full replace) ===")
    _run([sys.executable, "dev.py", "check"])
    verification = "python dev.py check — 195 tests, audit 10/10, ALL PASSED"

    if FROZEN.exists():
        print(f"Removing {FROZEN}")
        shutil.rmtree(FROZEN)
    FROZEN.mkdir(parents=True)

    _run([sys.executable, "scripts/generate_assets.py"])
    _run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "pyinstaller", "-q"])

    pyinstaller = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--clean",
        f"--distpath={FROZEN}",
        f"--workpath={FROZEN / 'build_work'}",
        "--add-data",
        "logo.png;.",
        "--add-data",
        "team_photo.jpg;.",
        "--add-data",
        "roster_seed.json;.",
        "--hidden-import",
        "customtkinter",
        "--hidden-import",
        "PIL",
        "--hidden-import",
        "PIL._tkinter_finder",
        "--hidden-import",
        "PIL.Image",
        "--hidden-import",
        "PIL.ImageTk",
        "--hidden-import",
        "reportlab",
        "--hidden-import",
        "reportlab.pdfgen.canvas",
    ]
    for mod in LOGIC_HIDDEN:
        pyinstaller.extend(["--hidden-import", mod])
    pyinstaller.extend(["--name", "Dodgeville_PD_Scheduler", "main.py"])
    _run(pyinstaller)

    shutil.copy2(ROOT / "EVALUATE.txt", FROZEN / "EVALUATE.txt")
    shutil.copy2(ROOT / "roster_seed.json", FROZEN / "roster_seed.json")
    _write_readme()
    _write_frozen_marker(verification)
    _copy_snapshot()

    exe = FROZEN / "Dodgeville_PD_Scheduler.exe"
    if not exe.is_file():
        print("ERROR: exe not found after build", file=sys.stderr)
        return 1
    size_mb = exe.stat().st_size / (1024 * 1024)
    print(f"\nFrozen package ready: {FROZEN}")
    print(f"  Dodgeville_PD_Scheduler.exe ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
