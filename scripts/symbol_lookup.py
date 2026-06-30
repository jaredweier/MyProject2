"""Find where a symbol is defined — avoid full-repo reads."""

from __future__ import annotations

import ast
import os
import re
import sys
from typing import Iterable, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_SEARCH_DIRS = ("logic", "ui", "validators.py", "config.py", "database.py", "cli.py", "audit.py")


def _iter_py_files(paths: Iterable[str]) -> List[str]:
    found: List[str] = []
    for entry in paths:
        full = os.path.join(ROOT, entry)
        if os.path.isfile(full) and entry.endswith(".py"):
            found.append(entry.replace("\\", "/"))
        elif os.path.isdir(full):
            for dirpath, _, names in os.walk(full):
                if any(skip in dirpath for skip in ("__pycache__", "build", "dist", ".git")):
                    continue
                for name in names:
                    if name.endswith(".py"):
                        rel = os.path.relpath(os.path.join(dirpath, name), ROOT)
                        found.append(rel.replace("\\", "/"))
    return sorted(set(found))


def _definitions_in_file(rel_path: str, symbol: str) -> List[Tuple[str, int]]:
    full = os.path.join(ROOT, rel_path)
    try:
        with open(full, encoding="utf-8", errors="replace") as fh:
            tree = ast.parse(fh.read(), filename=full)
    except (OSError, SyntaxError):
        return []

    hits: List[Tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == symbol:
            hits.append((f"class {symbol}", node.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
            hits.append((f"def {symbol}", node.lineno))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == symbol:
                    hits.append((f"{symbol} =", node.lineno))
    return hits


def lookup_symbol(
    symbol: str,
    *,
    search_paths: Iterable[str] | None = None,
    slice_id: str = "",
) -> List[Tuple[str, str, int]]:
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    paths = list(search_paths or [])
    if slice_id:
        from slices.registry import SLICES

        match = next((s for s in SLICES if s["id"] == slice_id), None)
        if match:
            paths = match.get("touch_together", paths)

    if not paths:
        paths = list(DEFAULT_SEARCH_DIRS)

    symbol = symbol.strip()
    if not symbol or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", symbol):
        return []

    results: List[Tuple[str, str, int]] = []
    for rel in _iter_py_files(paths):
        for kind, line in _definitions_in_file(rel, symbol):
            results.append((rel, kind, line))
    return results


def run_symbol_lookup(symbol: str, *, slice_id: str = "") -> int:
    os.chdir(ROOT)
    hits = lookup_symbol(symbol, slice_id=slice_id)
    print(f"symbol: {symbol}")
    print("=" * 60)
    if not hits:
        print("  No definitions found in scoped search.")
        print("  Try: python dev.py usage-brief <slice>  then re-run with --slice")
        print("  Or:  python dev.py outline <file>")
        return 1
    for rel, kind, line in hits[:20]:
        print(f"  {rel}:{line}  {kind}")
        print(f"    → python dev.py outline {rel}")
    if len(hits) > 20:
        print(f"  ... and {len(hits) - 20} more")
    print("=" * 60)
    print("Read outline first (~50 tokens), not the whole file.")
    return 0


if __name__ == "__main__":
    slice_id = ""
    args: List[str] = []
    for arg in sys.argv[1:]:
        if arg.startswith("--slice="):
            slice_id = arg.split("=", 1)[1]
        else:
            args.append(arg)
    if not args:
        print("Usage: python scripts/symbol_lookup.py <symbol> [--slice=id]")
        raise SystemExit(1)
    raise SystemExit(run_symbol_lookup(args[0], slice_id=slice_id))
