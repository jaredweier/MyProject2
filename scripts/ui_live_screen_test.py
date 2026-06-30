"""
Live on-screen UI test — visible window, auto-login, screenshots per step.

Uses an isolated test database by default (does not touch dodgeville_scheduler.db).

Run:
  python dev.py ui-live
  python dev.py ui-live --production   # your real DB, navigation/refresh only
  python dev.py ui-live --delay 1.0 --hold 10
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_LOCK_STALE_SECONDS = 600


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@contextmanager
def _ui_live_lock():
    from paths import data_path

    lock_path = data_path(os.path.join("logs", "ui_live_test", ".running.lock"))
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    if os.path.isfile(lock_path):
        stale = False
        try:
            with open(lock_path, encoding="utf-8") as fh:
                raw = fh.read().strip()
            lock_pid = int(raw) if raw.isdigit() else 0
            if lock_pid and not _pid_alive(lock_pid):
                stale = True
            elif time.time() - os.path.getmtime(lock_path) > _LOCK_STALE_SECONDS:
                stale = True
        except (OSError, ValueError):
            stale = True
        if stale:
            try:
                os.remove(lock_path)
            except OSError:
                pass
        else:
            print(
                f"Another ui-live run is already active (lock: {lock_path}). Wait for it to finish or delete the lock.",
                flush=True,
            )
            raise SystemExit(2)
    with open(lock_path, "w", encoding="utf-8") as fh:
        fh.write(str(os.getpid()))
    try:
        yield
    finally:
        try:
            os.remove(lock_path)
        except OSError:
            pass


def run_ui_live_screen(
    *,
    production: bool = False,
    step_delay: float = 0.65,
    hold_seconds: float = 6.0,
    mutating: bool | None = None,
) -> int:
    from paths import data_path
    from scripts.ui_exhaustive_test import run_ui_exhaustive

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shot_dir = data_path(os.path.join("logs", "ui_live_test", stamp))
    os.makedirs(shot_dir, exist_ok=True)

    if mutating is None:
        mutating = not production

    print("Dodgeville PD Scheduler — LIVE on-screen UI test", flush=True)
    print(f"  Database: {'production' if production else 'isolated test DB'}", flush=True)
    print(f"  Screenshots: {shot_dir}", flush=True)
    print(f"  Step delay: {step_delay}s  ·  Hold at end: {hold_seconds}s", flush=True)
    print("  Watch your screen — the app will cycle through every tab and feature.", flush=True)
    print("-" * 60, flush=True)

    with _ui_live_lock():
        code = run_ui_exhaustive(
            visible=True,
            step_delay=step_delay,
            screenshot_dir=shot_dir,
            isolated=not production,
            auto_login=False,
            mutating=mutating,
            hold_seconds=hold_seconds,
        )

    print("-" * 60, flush=True)
    print(f"Screenshots saved under: {shot_dir}", flush=True)
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live visible UI functionality test")
    parser.add_argument(
        "--production",
        action="store_true",
        help="Use your real database (read-only navigation; no create/delete steps)",
    )
    parser.add_argument("--delay", type=float, default=0.65, help="Seconds between steps")
    parser.add_argument("--hold", type=float, default=6.0, help="Seconds to keep window open at end")
    parser.add_argument(
        "--mutating",
        action="store_true",
        help="With --production: run create/approve/delete steps (default off for production)",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Navigation and refresh only (no create/delete even on test DB)",
    )
    args = parser.parse_args(argv)
    mutating = None
    if args.read_only:
        mutating = False
    elif args.mutating:
        mutating = True
    return run_ui_live_screen(
        production=args.production,
        step_delay=args.delay,
        hold_seconds=args.hold,
        mutating=mutating,
    )


if __name__ == "__main__":
    raise SystemExit(main())
