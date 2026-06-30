"""Rough token estimates for files and text (chars / 4 heuristic)."""

from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def file_stats(rel_path: str) -> dict:
    full = os.path.join(ROOT, rel_path)
    if not os.path.isfile(full):
        return {"path": rel_path, "exists": False, "bytes": 0, "lines": 0, "tokens": 0}
    with open(full, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    lines = text.count("\n") + (1 if text else 0)
    return {
        "path": rel_path,
        "exists": True,
        "bytes": os.path.getsize(full),
        "lines": lines,
        "tokens": estimate_tokens(text),
    }


def format_stats_row(stats: dict) -> str:
    if not stats.get("exists"):
        return f"  {stats['path']} (missing)"
    kb = stats["bytes"] / 1024
    return f"  {stats['path']}: {stats['lines']} lines, {kb:.1f} KB, ~{stats['tokens']:,} tokens"
