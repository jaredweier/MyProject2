"""Fast pre-commit gate — imports, slice bindings, audit, optional refactor-check."""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_preflight(with_refactor: bool = False) -> int:
    dev_py = os.path.join(ROOT, "dev.py")
    steps = ["imports", "slice-check", "audit"]
    if with_refactor:
        steps.append("refactor-check")

    print("Dodgeville PD Scheduler — preflight")
    print("=" * 60)
    failed: list[str] = []
    for name in steps:
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
        print(f"preflight: FAILED — {', '.join(failed)}")
        return 1
    print("preflight: ALL PASSED")
    return 0


if __name__ == "__main__":
    with_refactor = "--with-refactor" in sys.argv
    raise SystemExit(run_preflight(with_refactor=with_refactor))
