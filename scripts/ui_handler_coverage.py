"""
Report UI handler coverage — maps command= handlers in ui/ to exhaustive test steps.

Run: python dev.py ui-handler-coverage
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DIR = os.path.join(ROOT, "ui")


def _collect_ui_commands() -> dict[str, list[str]]:
    pattern = re.compile(r"command\s*=\s*(?:self\.|lambda[^:]*:\s*self\.)?([a-zA-Z_][\w]*)")
    by_file: dict[str, list[str]] = {}
    for name in sorted(os.listdir(UI_DIR)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(UI_DIR, name)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        hits = sorted(set(pattern.findall(text)))
        handlers = [
            h
            for h in hits
            if not h.startswith("_")
            or h
            in (
                "_bulk_approve_requests",
                "_bulk_reject_requests",
                "_export_gantt_pdf",
                "_show_my_profile",
                "_refresh_current_page",
            )
        ]
        public = sorted(set(hits))
        if public:
            by_file[name] = public
    return by_file


def _collect_test_steps() -> list[str]:
    test_path = os.path.join(ROOT, "scripts", "ui_exhaustive_test.py")
    ext_path = os.path.join(ROOT, "scripts", "ui_extended_handlers.py")
    steps: list[str] = []
    for path in (test_path, ext_path):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        steps.extend(re.findall(r'_run_step\("([^"]+)"|run_step\("([^"]+)"', text))
    flat = []
    for a, b in steps:
        flat.append(a or b)
    return flat


def run_ui_handler_coverage() -> int:
    commands = _collect_ui_commands()
    steps = _collect_test_steps()
    step_blob = " ".join(steps).lower()

    print("Dodgeville PD Scheduler — UI handler coverage")
    print("=" * 60)
    print(f"Exhaustive test steps: {len(steps)}")
    print(f"UI files with command= handlers: {len(commands)}")
    print("-" * 60)

    all_handlers: list[str] = []
    for handlers in commands.values():
        all_handlers.extend(handlers)
    unique = sorted(set(all_handlers))

    covered = 0
    for handler in unique:
        token = handler.replace("_", " ").lower()
        short = handler.lstrip("_").replace("_", "")
        if handler in step_blob or short in step_blob.replace(" ", "") or any(handler in s for s in steps):
            covered += 1

    print(f"Named handlers referenced in tests (approx): {covered}/{len(unique)}")
    print("Step list includes role sessions (supervisor/officer) and extended toolbar coverage.")
    print("=" * 60)
    print("Run: python dev.py ui-exhaustive   (81 steps)")
    print("Run: python dev.py ui-live         (visible + screenshots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_ui_handler_coverage())
