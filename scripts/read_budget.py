"""Estimate tokens before reading files — free gate to avoid whole-file waste."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
CHARS_PER_TOKEN = 4
SOFT_WARN = 2500  # tokens — prefer outline/symbol above this
HARD_WARN = 8000


def estimate_path(rel: str) -> Tuple[str, int, int, str]:
    path = ROOT / rel
    if not path.is_file():
        return rel, 0, 0, "missing"
    raw = path.read_bytes()
    chars = len(raw)
    tokens = max(1, chars // CHARS_PER_TOKEN)
    lines = raw.count(b"\n") + (1 if raw and not raw.endswith(b"\n") else 0)
    if tokens >= HARD_WARN:
        advice = "outline/symbol ONLY — do not full-read"
    elif tokens >= SOFT_WARN:
        advice = "outline first; full-read only if editing this file"
    else:
        advice = "ok to read if in slice touch_together"
    return rel, lines, tokens, advice


def run_read_budget(paths: List[str], *, as_json: bool = False) -> int:
    rows = [estimate_path(p.replace("\\", "/")) for p in paths]
    total = sum(r[2] for r in rows)
    if as_json:
        import json

        print(
            json.dumps(
                {
                    "files": [{"path": p, "lines": n, "tokens": t, "advice": a} for p, n, t, a in rows],
                    "total_tokens": total,
                    "soft_warn": SOFT_WARN,
                    "hard_warn": HARD_WARN,
                },
                indent=2,
            )
        )
        return 0

    print("Dodgeville PD — read budget (free, no LLM)")
    print("=" * 56)
    for p, n, t, a in rows:
        flag = "!" if t >= SOFT_WARN else " "
        print(f" {flag} {t:6,}t  {n:5}L  {p}")
        print(f"     → {a}")
    print("-" * 56)
    print(f"  TOTAL ~{total:,} tokens if all full-read")
    if total >= HARD_WARN:
        print("  Prefer: python dev.py outline <file> | symbol <name> | usage-brief <slice>")
        return 2
    if total >= SOFT_WARN:
        print("  Prefer outlines for largest files before any full read.")
        return 1
    print("  Budget OK for slice-scoped work.")
    return 0


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("paths", nargs="+", help="Repo-relative Python/doc paths")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    os.chdir(ROOT)
    return run_read_budget(args.paths, as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
