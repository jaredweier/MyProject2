"""Dependency vulnerability scan via pip-audit (PyPI advisory DB)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _audit_one(req_path: str) -> int:
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

    result = subprocess.run(argv, cwd=ROOT)
    return result.returncode


def run_deps_audit(*, requirements: str = "requirements.txt", extra_requirements: str = "requirements-dev.txt") -> int:
    os.chdir(ROOT)
    req_path = os.path.join(ROOT, requirements)
    if not os.path.isfile(req_path):
        print(f"deps-audit: missing {requirements}")
        return 1

    targets = [requirements]
    extra_path = os.path.join(ROOT, extra_requirements) if extra_requirements else None
    if extra_path and os.path.isfile(extra_path):
        targets.append(extra_requirements)

    print("Dodgeville PD Scheduler — deps-audit (pip-audit)")
    print("=" * 60)
    worst = 0
    for target in targets:
        print(f"-- {target} --")
        code = _audit_one(os.path.join(ROOT, target))
        worst = max(worst, code)
    print("=" * 60)
    if worst == 0:
        print("deps-audit: ALL PASSED")
    else:
        print("deps-audit: ISSUES FOUND — review output above")
    return worst


if __name__ == "__main__":
    req = "requirements.txt"
    extra_req = "requirements-dev.txt"
    for arg in sys.argv[1:]:
        if arg.startswith("--requirements="):
            req = arg.split("=", 1)[1]
        elif arg.startswith("--extra-requirements="):
            extra_req = arg.split("=", 1)[1]
    raise SystemExit(run_deps_audit(requirements=req, extra_requirements=extra_req))
