"""Install git pre-commit hooks — full framework when available, simple fallback otherwise."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_BODY = """#!/bin/sh
# Dodgeville PD Scheduler — auto-installed by scripts/install_pre_commit.py
cd "$(git rev-parse --show-toplevel)" || exit 1
python dev.py preflight || exit 1
"""


def _install_simple_hook() -> int:
    git_dir = os.path.join(ROOT, ".git")
    if not os.path.isdir(git_dir):
        print("Not a git repository — cannot install pre-commit hook.")
        return 1

    hooks_dir = os.path.join(git_dir, "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    hook_path = os.path.join(hooks_dir, "pre-commit")

    with open(hook_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(HOOK_BODY)

    mode = os.stat(hook_path).st_mode
    os.chmod(hook_path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Installed simple pre-commit hook: {hook_path}")
    print("Runs: python dev.py preflight")
    return 0


def install() -> int:
    if shutil.which("pre-commit"):
        result = subprocess.run(
            ["pre-commit", "install"],
            cwd=ROOT,
        )
        if result.returncode == 0:
            print("Installed pre-commit framework hooks (.pre-commit-config.yaml)")
            print("Hooks: ruff, codespell, yaml checks, dodgeville preflight")
            return 0
        print("pre-commit install failed — falling back to simple hook")

    return _install_simple_hook()


if __name__ == "__main__":
    raise SystemExit(install())
