"""
Build a portable Dodgeville PD Scheduler package for any Windows PC.

No Python required on the target machine — copy folder (or unzip) and run
START HERE.bat.

Run:
  python scripts/build_portable.py
  python scripts/build_portable.py --quick
  python dev.py build-portable
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
PACKAGE = DIST / "Dodgeville_PD_Portable"
APP_DIR = PACKAGE / "Dodgeville_PD_Scheduler"

HIDDEN_IMPORTS = [
    "customtkinter",
    "PIL",
    "PIL._tkinter_finder",
    "PIL.Image",
    "PIL.ImageTk",
    "reportlab",
    "reportlab.pdfgen.canvas",
    "scheduler_core",
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
    "logic.analytics",
    "logic.rotation_preview",
    "logic.rust_bridge",
    "logic.rust_fallback",
    "logic.labor_compliance",
    "analytics",
    "exports",
    "simulator",
]

DEPLOY_FILES = [
    ("docs/deploy/START HERE.bat", "START HERE.bat"),
    ("docs/deploy/GETTING STARTED.txt", "GETTING STARTED.txt"),
    ("docs/deploy/IT_INSTALL.txt", "IT_INSTALL.txt"),
    ("docs/deploy/Supervisor_Quick_Start.txt", "Supervisor_Quick_Start.txt"),
    ("docs/deploy/Officer_Quick_Start.txt", "Officer_Quick_Start.txt"),
    ("EVALUATE.txt", "EVALUATE.txt"),
    ("roster_seed.json", "roster_seed.json"),
]


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=cwd or ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _pyinstaller_cmd(*, quick: bool) -> list[str]:
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--clean",
        f"--distpath={PACKAGE}",
        f"--workpath={DIST / 'build_work'}",
        f"--specpath={ROOT}",
        "--add-data",
        "roster_seed.json;.",
        "--collect-all",
        "scheduler_core",
        "--collect-all",
        "customtkinter",
    ]
    for mod in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", mod])
    cmd.extend(["--name", "Dodgeville_PD_Scheduler", "main.py"])
    return cmd


def _write_build_info(*, verification: str) -> None:
    from config import APP_NAME, APP_VERSION

    text = f"""{APP_NAME} — Portable build
Version: {APP_VERSION}
Build date: {date.today().isoformat()}
Built at: {datetime.now(timezone.utc).isoformat()}
Source: {ROOT}
Verification: {verification}

Target: Windows 10/11 (64-bit). No Python install required.

Run: START HERE.bat
Docs: GETTING STARTED.txt · IT_INSTALL.txt · Supervisor_Quick_Start.txt · Officer_Quick_Start.txt
"""
    (PACKAGE / "BUILD_INFO.txt").write_text(text, encoding="utf-8", newline="\n")


def _stage_launcher_files() -> None:
    for src_rel, dest_name in DEPLOY_FILES:
        src = ROOT / src_rel
        if not src.is_file():
            raise SystemExit(f"Missing deploy file: {src}")
        shutil.copy2(src, PACKAGE / dest_name)


def _make_zip() -> Path:
    stamp = date.today().strftime("%Y%m%d")
    zip_path = DIST / f"Dodgeville_PD_Portable_{stamp}.zip"
    if zip_path.is_file():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for folder, _, files in os.walk(PACKAGE):
            for name in files:
                full = Path(folder) / name
                arc = full.relative_to(PACKAGE.parent)
                zf.write(full, arc.as_posix())
    return zip_path


def build_portable(*, quick: bool = False, zip_package: bool = True) -> int:
    print("=== Dodgeville PD Scheduler — portable package ===", flush=True)
    if not quick:
        _run([sys.executable, "dev.py", "check"])
        verification = "python dev.py check — ALL PASSED"
    else:
        _run([sys.executable, "dev.py", "doctor"])
        verification = "python dev.py doctor — quick build (tests skipped)"

    try:
        import scheduler_core  # noqa: F401
    except ImportError:
        print("scheduler_core not built — running build-rust...", flush=True)
        _run([sys.executable, "dev.py", "build-rust"])

    from logic import rust_bridge

    if rust_bridge.backend_name() != "rust":
        print(
            f"ERROR: portable build requires Rust scheduler_core (got {rust_bridge.backend_name()!r})",
            file=sys.stderr,
        )
        return 1

    _run([sys.executable, "scripts/generate_assets.py"])
    _run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "pyinstaller", "-q"])

    if PACKAGE.exists():
        print(f"Removing previous package: {PACKAGE}", flush=True)
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True, exist_ok=True)

    _run(_pyinstaller_cmd(quick=quick))

    exe = APP_DIR / "Dodgeville_PD_Scheduler.exe"
    if not exe.is_file():
        print(f"ERROR: exe not found at {exe}", file=sys.stderr)
        return 1

    _stage_launcher_files()
    _write_build_info(verification=verification)

    zip_path = None
    if zip_package:
        zip_path = _make_zip()
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"\nZip for sharing: {zip_path} ({size_mb:.1f} MB)", flush=True)

    exe_mb = exe.stat().st_size / (1024 * 1024)
    print(f"\nPortable package ready: {PACKAGE}", flush=True)
    print(f"  Double-click: {PACKAGE / 'START HERE.bat'}", flush=True)
    print(f"  App exe: {exe} ({exe_mb:.1f} MB)", flush=True)
    print("\nCopy the Dodgeville_PD_Portable folder OR the .zip to any Windows PC.", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build portable scheduler package")
    parser.add_argument("--quick", action="store_true", help="Skip full test gate (doctor only)")
    parser.add_argument("--no-zip", action="store_true", help="Do not create dist/*.zip")
    args = parser.parse_args(argv)
    return build_portable(quick=args.quick, zip_package=not args.no_zip)


if __name__ == "__main__":
    raise SystemExit(main())
