"""Install local token-minimization hooks (git + verify Cursor hooks)."""

from __future__ import annotations

import os
import stat
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GIT_HOOK_BODY = """#!/bin/sh
# Dodgeville PD — refresh agent context after checkout/merge
cd "$(git rev-parse --show-toplevel)" 2>/dev/null || exit 0
if [ "$SCHEDULER_SKIP_AGENT_GATES" = "1" ]; then exit 0; fi
python dev.py agent-gates -q 2>/dev/null || python scripts/agent_gates.py --force -q 2>/dev/null || true
exit 0
"""


def _write_executable(path: str, body: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    mode = os.stat(path).st_mode
    os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install_git_refresh_hooks() -> int:
    git_dir = os.path.join(ROOT, ".git")
    if not os.path.isdir(git_dir):
        print("install-local-minimize: not a git repo — skipped git hooks")
        return 0

    hooks_dir = os.path.join(git_dir, "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    for name in ("post-checkout", "post-merge"):
        path = os.path.join(hooks_dir, name)
        _write_executable(path, GIT_HOOK_BODY)
        print(f"  installed {path}")
    return 0


def verify_cursor_hooks() -> bool:
    required = (
        ".cursor/hooks.json",
        ".cursor/hooks/before_read_file.py",
        ".cursor/hooks/session_start.py",
    )
    ok = all(os.path.isfile(os.path.join(ROOT, p)) for p in required)
    if ok:
        print("  Cursor hooks: ok (.cursor/hooks.json)")
    else:
        print("  Cursor hooks: MISSING — reload project in Cursor")
    return ok


def install(*, refresh_pack: bool = True) -> int:
    os.chdir(ROOT)
    print("Dodgeville PD — install local token minimization")
    print("-" * 40)

    install_git_refresh_hooks()
    verify_cursor_hooks()

    if refresh_pack:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        try:
            from scripts.agent_gates import run_agent_gates

            run_agent_gates(source="install", command="install-local-minimize", quiet=False, force=True, debounce_sec=0)
        except Exception as exc:
            print(f"  agent-pack refresh failed: {exc}")

    print("-" * 40)
    print("Done. Cursor: reload window to activate hooks.")
    print("Skip anytime: set SCHEDULER_SKIP_AGENT_GATES=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(install())
