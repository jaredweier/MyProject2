"""Find large indexable files not excluded by .cursorignore — reduce surprise token cost."""

from __future__ import annotations

import fnmatch
import os
from typing import List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {
    ".git",
    "dist",
    "build",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "rust",
    "terminals",
}


def _load_ignore_patterns() -> List[str]:
    path = os.path.join(ROOT, ".cursorignore")
    if not os.path.isfile(path):
        return []
    patterns: List[str] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line.replace("\\", "/"))
    return patterns


def _ignored(rel: str, patterns: List[str]) -> bool:
    rel = rel.replace("\\", "/")
    for pat in patterns:
        p = pat.rstrip("/")
        if pat.endswith("/"):
            if rel.startswith(p + "/") or rel == p:
                return True
        elif "*" in pat or "?" in pat:
            if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(os.path.basename(rel), pat):
                return True
        elif rel == p or rel.startswith(p + "/"):
            return True
    return False


def scan_large_files(*, min_kb: int = 100, limit: int = 25) -> Tuple[List[dict], List[dict]]:
    patterns = _load_ignore_patterns()
    indexed_large: List[dict] = []
    ignored_large: List[dict] = []

    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, ROOT).replace("\\", "/")
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size < min_kb * 1024:
                continue
            entry = {
                "path": rel,
                "kb": round(size / 1024, 1),
                "tokens": max(1, size // 4),
            }
            if _ignored(rel, patterns):
                ignored_large.append(entry)
            else:
                indexed_large.append(entry)

    indexed_large.sort(key=lambda x: x["kb"], reverse=True)
    ignored_large.sort(key=lambda x: x["kb"], reverse=True)
    return indexed_large[:limit], ignored_large[:limit]


def run_token_scan(*, min_kb: int = 100) -> int:
    os.chdir(ROOT)
    indexed, ignored = scan_large_files(min_kb=min_kb)

    print("Dodgeville PD — token scan (index vs cursorignore)")
    print("=" * 60)
    print(f"Threshold: {min_kb} KB+")
    print("\n⚠ Still indexable (add to .cursorignore if not needed every turn):")
    if indexed:
        for e in indexed:
            print(f"  {e['path']}: {e['kb']} KB (~{e['tokens']:,} tokens)")
    else:
        print("  (none — good)")

    print("\n✓ Large but already ignored (sample):")
    for e in ignored[:8]:
        print(f"  {e['path']}: {e['kb']} KB")
    if len(ignored) > 8:
        print(f"  ... {len(ignored) - 8} more")

    print("\n" + "=" * 60)
    if indexed:
        print(f"token-scan: {len(indexed)} large indexable file(s) — consider .cursorignore")
        return 1
    print("token-scan: no large surprise index files")
    return 0


if __name__ == "__main__":
    import sys

    kb = 100
    for arg in sys.argv[1:]:
        if arg.startswith("--min-kb="):
            kb = int(arg.split("=", 1)[1])
    raise SystemExit(run_token_scan(min_kb=kb))
