"""Shared read-guard rules for Cursor hooks and token tooling."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Hard block — never send to LLM
BLOCK_SUBSTRINGS = (
    "FULL_PROJECT_CODE",
    ".grok/sessions/",
    "tests/ui_snapshots/baseline/",
    "/baseline/",
    ".git/",
)

BLOCK_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".db", ".ics")

# Soft guard — prompt outline first
LARGE_FILE_KB = 55


@dataclass
class ReadGuardResult:
    action: str  # allow | deny | ask
    reason: str
    agent_message: str = ""
    user_message: str = ""


def _norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def check_read(path: str, *, root: str = ROOT) -> ReadGuardResult:
    rel = _norm(path)
    lower = rel.lower()

    for sub in BLOCK_SUBSTRINGS:
        if sub.lower() in lower:
            return ReadGuardResult(
                action="deny",
                reason=f"blocked path pattern: {sub}",
                user_message=f"Blocked read: {rel}",
                agent_message=(
                    f"Do not read `{rel}`. Use `@logs/agent_pack/latest.md` and "
                    "`python dev.py outline <file>` for scoped context."
                ),
            )

    ext = os.path.splitext(rel)[1].lower()
    if ext in BLOCK_EXTENSIONS:
        return ReadGuardResult(
            action="deny",
            reason=f"blocked extension {ext}",
            user_message=f"Blocked binary/asset read: {rel}",
            agent_message=f"Do not load `{rel}` into context. Use text reports in logs/ only.",
        )

    full = os.path.join(root, rel) if not os.path.isabs(path) else path
    if os.path.isfile(full):
        kb = os.path.getsize(full) / 1024
        if kb >= LARGE_FILE_KB and rel.endswith(".py"):
            return ReadGuardResult(
                action="ask",
                reason=f"large file {kb:.0f}KB",
                user_message=f"Large file ({kb:.0f} KB): approve only if outline insufficient",
                agent_message=(
                    f"`{rel}` is ~{int(kb * 256):,} tokens whole. "
                    f"Run first: `python dev.py outline {rel}` or `python dev.py symbol <name> --slice <id>`"
                ),
            )

    try:
        from scripts.context_window import register_tool_from_read

        register_tool_from_read(rel, root=root)
    except Exception:
        pass

    return ReadGuardResult(action="allow", reason="ok")


def known_large_ui_files(*, root: str = ROOT) -> list[tuple[str, float]]:
    """Large indexable UI modules — prefer outline in agent-pack."""
    ui = os.path.join(root, "ui")
    if not os.path.isdir(ui):
        return []
    out: list[tuple[str, float]] = []
    for name in os.listdir(ui):
        if not name.endswith(".py"):
            continue
        full = os.path.join(ui, name)
        kb = os.path.getsize(full) / 1024
        if kb >= LARGE_FILE_KB:
            out.append((f"ui/{name}", kb))
    return sorted(out, key=lambda x: -x[1])
