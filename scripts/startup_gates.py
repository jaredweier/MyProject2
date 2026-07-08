"""
Automatic startup gates — run cheap-check (and optional preflight) on app/dev use.

Skips when SCHEDULER_SKIP_STARTUP_GATES=1. Debounces rapid dev.py calls.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "logs", "last_gate.json")
DEBOUNCE_SEC = 90


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_state() -> dict:
    if not os.path.isfile(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_state(*, passed: bool, mode: str, source: str, command: str = "") -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    payload = {
        "timestamp": _utc_now(),
        "passed": passed,
        "mode": mode,
        "source": source,
        "command": command,
    }
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def _should_debounce(debounce_sec: int) -> bool:
    if debounce_sec <= 0:
        return False
    state = _read_state()
    ts = state.get("timestamp")
    if not ts or not state.get("passed"):
        return False
    try:
        then = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - then).total_seconds()
        return age < debounce_sec
    except ValueError:
        return False


def ensure_pre_commit_hook() -> None:
    if os.environ.get("SCHEDULER_SKIP_PRECOMMIT_INSTALL", "").strip() in ("1", "true", "yes"):
        return
    hook = os.path.join(ROOT, ".git", "hooks", "pre-commit")
    if os.path.isfile(hook):
        return
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        return
    try:
        from scripts.install_pre_commit import install

        install()
    except Exception:
        pass


def ensure_local_minimize_hooks() -> None:
    if os.environ.get("SCHEDULER_SKIP_LOCAL_MINIMIZE_INSTALL", "").strip() in ("1", "true", "yes"):
        return
    marker = os.path.join(ROOT, "logs", ".local_minimize_installed")
    if os.path.isfile(marker):
        return
    if not os.path.isfile(os.path.join(ROOT, ".cursor", "hooks.json")):
        return
    try:
        from scripts.install_local_minimize import install_git_refresh_hooks, verify_cursor_hooks

        install_git_refresh_hooks()
        verify_cursor_hooks()
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write("ok\n")
    except Exception:
        pass


def run_startup_gates(
    *,
    source: str = "app",
    command: str = "",
    full: bool = False,
    quiet: bool = False,
    debounce_sec: int = DEBOUNCE_SEC,
    ensure_hook: bool = True,
) -> int:
    if os.environ.get("SCHEDULER_SKIP_STARTUP_GATES", "").strip().lower() in ("1", "true", "yes"):
        return 0

    # Frozen .exe cannot subprocess dev.py (sys.executable is the bundle, not Python).
    try:
        from paths import is_frozen

        if is_frozen():
            return 0
    except ImportError:
        if getattr(sys, "frozen", False):
            return 0

    if _should_debounce(debounce_sec):
        return 0

    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    os.chdir(ROOT)

    if ensure_hook:
        ensure_pre_commit_hook()
        ensure_local_minimize_hooks()

    full = full or os.environ.get("SCHEDULER_STARTUP_FULL", "").strip().lower() in ("1", "true", "yes")

    if not quiet:
        print("Dodgeville PD — startup gates (automatic)")
        print("-" * 40)

    from scripts.verify import run_fast
    from scripts.verify import run_preflight as verify_preflight

    if full:
        code = verify_preflight(source=source or "startup-gates", with_refactor=False)
        mode = "preflight"
    else:
        code = run_fast(source=source or "startup-gates")
        mode = "fast"

    passed = code == 0
    _write_state(passed=passed, mode=mode, source=source, command=command)

    if not quiet and not passed:
        print("startup-gates: FAILED — run: python dev.py fix-hint")

    return code


# dev.py commands that should not trigger auto-gates (they are gates or meta)
DEV_SKIP_AUTO_GATES = frozenset(
    {
        None,
        "startup-gates",
        "cheap-check",
        "preflight",
        "verify",
        "readiness-check",
        "fix-hint",
        "usage-brief",
        "route-task",
        "lint",
        "deps-audit",
        "token-audit",
        "token-scan",
        "agent-gates",
        "install-local-minimize",
        "agent-pack",
        "outline",
        "symbol",
        "imports",
        "audit",
        "slice-map",
        "feature-map",
        "logic-imports",
    }
)

# dev.py commands that run full preflight instead of cheap-check first
DEV_FULL_GATE_COMMANDS = frozenset(
    {
        "verify-features",
        "ui-exhaustive",
    }
)


def auto_before_dev_command(command: Optional[str]) -> int:
    if command in DEV_SKIP_AUTO_GATES:
        return 0
    full = command in DEV_FULL_GATE_COMMANDS
    return run_startup_gates(
        source="dev.py",
        command=command or "",
        full=full,
        quiet=True,
        debounce_sec=DEBOUNCE_SEC,
    )


def auto_before_gui() -> int:
    return run_startup_gates(
        source="main.py",
        full=False,
        quiet=True,
        debounce_sec=0,
    )


def auto_before_cli() -> int:
    return run_startup_gates(
        source="cli.py",
        full=False,
        quiet=True,
        debounce_sec=DEBOUNCE_SEC,
    )


def gui_gate_warning_if_failed(parent=None) -> None:
    """Show non-blocking warning if last startup gate failed."""
    state = _read_state()
    if state.get("passed", True):
        return
    try:
        import customtkinter as ctk

        msg = (
            "Automatic health check failed before launch.\n\n"
            "Run in project folder:\n"
            "  python dev.py fix-hint\n"
            "  python dev.py verify --tier check\n\n"
            "Set SCHEDULER_SKIP_STARTUP_GATES=1 to skip auto checks."
        )
        if parent is not None:
            dlg = ctk.CTkToplevel(parent)
            dlg.title("Startup check")
            dlg.geometry("480x220")
            ctk.CTkLabel(dlg, text=msg, wraplength=440, justify="left").pack(padx=16, pady=16)
            ctk.CTkButton(dlg, text="Continue", command=dlg.destroy).pack(pady=8)
        else:
            print(msg)
    except Exception:
        print("Startup gate failed — see logs/last_gate.json")


if __name__ == "__main__":
    full = "--full" in sys.argv
    quiet = "--quiet" in sys.argv or "-q" in sys.argv
    raise SystemExit(run_startup_gates(full=full, quiet=quiet, debounce_sec=0))
