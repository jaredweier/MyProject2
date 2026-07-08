"""
Automatic agent token-minimization gates.

Refreshes logs/agent_pack/latest.md and enforces scoped context on dev.py use.
Skips when SCHEDULER_SKIP_AGENT_GATES=1.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "logs", "last_agent_gate.json")
PACK_PATH = os.path.join(ROOT, "logs", "agent_pack", "latest.md")
DEBOUNCE_SEC = 90

# dev.py commands that skip auto agent-pack refresh
DEV_SKIP_AGENT_GATES = frozenset(
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
        "context-window",
        "batch-process",
        "outline",
        "symbol",
        "imports",
        "audit",
        "slice-map",
        "feature-map",
        "logic-imports",
        "doctor",
        "help",
    }
)


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


def _write_state(*, slice_id: str, command: str, source: str, pack_tokens: int) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    payload = {
        "timestamp": _utc_now(),
        "slice_id": slice_id,
        "command": command,
        "source": source,
        "pack_path": "logs/agent_pack/latest.md",
        "pack_tokens": pack_tokens,
        "mandate": "logs/agent_pack/latest.md + docs/AGENT_STABLE.md",
    }
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def _should_debounce(debounce_sec: int) -> bool:
    if debounce_sec <= 0:
        return False
    state = _read_state()
    ts = state.get("timestamp")
    if not ts:
        return False
    try:
        then = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - then).total_seconds()
        return age < debounce_sec
    except ValueError:
        return False


def _git_changed_files() -> list[str]:
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        return []
    files: list[str] = []
    for argv in (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--name-only", "--cached"],
        ["git", "ls-files", "--modified", "--others", "--exclude-standard"],
    ):
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
        if result.returncode == 0:
            files.extend(line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip())
    return sorted(set(files))


def detect_slice_id(*, env_slice: str = "") -> str:
    if env_slice.strip():
        return env_slice.strip()

    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from slices.registry import SLICES

    changed = _git_changed_files()
    if not changed:
        return ""

    best_id = ""
    best_score = 0
    for s in SLICES:
        touch = [t.replace("\\", "/") for t in s.get("touch_together", [])]
        score = 0
        for path in changed:
            for t in touch:
                if path == t or path.endswith("/" + t) or path.startswith(t):
                    score += len(t)
        if score > best_score:
            best_score = score
            best_id = s["id"]
    return best_id


def run_agent_gates(
    *,
    source: str = "dev.py",
    command: str = "",
    task: str = "",
    slice_id: str = "",
    quiet: bool = True,
    debounce_sec: int = DEBOUNCE_SEC,
    force: bool = False,
) -> int:
    if os.environ.get("SCHEDULER_SKIP_AGENT_GATES", "").strip().lower() in ("1", "true", "yes"):
        return 0

    if not force and _should_debounce(debounce_sec):
        return 0

    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    os.chdir(ROOT)

    env_slice = os.environ.get("SCHEDULER_SLICE", "").strip()
    resolved_slice = slice_id or detect_slice_id(env_slice=env_slice)
    resolved_task = task or os.environ.get("SCHEDULER_AGENT_TASK", "").strip()

    from scripts.agent_pack import build_agent_pack

    content = build_agent_pack(task=resolved_task, slice_id=resolved_slice)
    os.makedirs(os.path.dirname(PACK_PATH), exist_ok=True)
    with open(PACK_PATH, "w", encoding="utf-8") as fh:
        fh.write(content)

    from scripts.agent_pack import build_agent_pack_json

    compact_path = os.path.join(ROOT, "logs", "agent_pack", "compact.json")
    with open(compact_path, "w", encoding="utf-8") as fh:
        json.dump(
            build_agent_pack_json(
                task=resolved_task,
                slice_id=resolved_slice,
                complexity="",
            ),
            fh,
            indent=2,
        )

    pack_tokens = max(1, len(content) // 4)
    _write_state(
        slice_id=resolved_slice,
        command=command,
        source=source,
        pack_tokens=pack_tokens,
    )

    if not quiet:
        print("Dodgeville PD — agent gates (automatic token minimization)")
        print("-" * 40)
        print(f"Context pack: logs/agent_pack/latest.md (~{pack_tokens:,} tokens)")
        if resolved_slice:
            print(f"Slice: {resolved_slice}")
        print("Agents: @logs/agent_pack/latest.md + @docs/AGENT_STABLE.md")

    return 0


def auto_before_dev_command(command: Optional[str]) -> int:
    if command in DEV_SKIP_AGENT_GATES:
        return 0
    return run_agent_gates(
        source="dev.py",
        command=command or "",
        quiet=True,
        debounce_sec=DEBOUNCE_SEC,
    )


def auto_before_session() -> int:
    return run_agent_gates(
        source="session-start",
        command="session-start",
        quiet=False,
        debounce_sec=0,
        force=True,
    )


def auto_after_route_task(task: str, slice_id: str = "") -> int:
    return run_agent_gates(
        source="route-task",
        command="route-task",
        task=task,
        slice_id=slice_id,
        quiet=True,
        debounce_sec=0,
        force=True,
    )


def agent_context_hint() -> str:
    """One-line hint for agents (paste into logs or print)."""
    state = _read_state()
    tokens = state.get("pack_tokens", "?")
    return f"@logs/agent_pack/latest.md (~{tokens}t) + @docs/AGENT_STABLE.md"


if __name__ == "__main__":
    force = "--force" in sys.argv
    quiet = "--quiet" in sys.argv or "-q" in sys.argv
    slice_id = ""
    for arg in sys.argv[1:]:
        if arg.startswith("--slice="):
            slice_id = arg.split("=", 1)[1]
    raise SystemExit(run_agent_gates(slice_id=slice_id, quiet=not quiet, force=force, debounce_sec=0))
