"""Dependency vulnerability scan via pip-audit (PyPI advisory DB)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_deps_audit(*, requirements: str = "requirements.txt") -> int:
    os.chdir(ROOT)
    req_path = os.path.join(ROOT, requirements)
    if not os.path.isfile(req_path):
        print(f"deps-audit: missing {requirements}")
        return 1

    exe = shutil.which("pip-audit")
    if exe is None:
        try:
            import pip_audit  # noqa: F401

            argv = [sys.executable, "-m", "pip_audit", "-r", req_path]
        except ImportError:
            print("deps-audit: pip-audit not installed")
            print("  pip install -r requirements-dev.txt")
            return 1
    else:
        argv = [exe, "-r", req_path]

    print("Dodgeville PD Scheduler — deps-audit (pip-audit)")
    print("=" * 60)
    result = subprocess.run(argv, cwd=ROOT)
    print("=" * 60)
    if result.returncode == 0:
        print("deps-audit: ALL PASSED")
    else:
        print("deps-audit: ISSUES FOUND — review output above")
    return result.returncode


if __name__ == "__main__":
    req = "requirements.txt"
    for arg in sys.argv[1:]:
        if arg.startswith("--requirements="):
            req = arg.split("=", 1)[1]
    raise SystemExit(run_deps_audit(requirements=req))
