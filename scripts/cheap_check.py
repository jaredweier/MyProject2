"""Ultra-fast gate (~5s): imports + audit only — zero LLM cost."""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cheap_check() -> int:
    dev_py = os.path.join(ROOT, "dev.py")
    print("Dodgeville PD Scheduler — cheap-check (free)")
    print("=" * 60)
    failed: list[str] = []
    for name in ("imports", "audit"):
        print(f"\n>>> {name}", flush=True)
        result = subprocess.run(
            [sys.executable, dev_py, name],
            cwd=ROOT,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            failed.append(name)
    print("\n" + "=" * 60)
    if failed:
        print(f"cheap-check: FAILED — {', '.join(failed)}")
        print("Next: python dev.py fix-hint")
        return 1
    print("cheap-check: ALL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cheap_check())
