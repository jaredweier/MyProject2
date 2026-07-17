"""Verify all `logic` imports resolve against logic.py exports."""

from __future__ import annotations

import ast
import importlib
import os
import re
import sys
from typing import Dict, Iterable, List, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCAN_DIRS = ("ui", "cli.py", "analytics.py", "simulator.py", "tests", "scripts")
SKIP_FILES = {
    "audit_logic_imports.py",
    "rebuild_logic_monolith.py",
    "split_logic_package.py",
    "extract_ui_mixins.py",
    "rebuild_ui_mixins.py",
}


def _logic_exports() -> Set[str]:
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from scripts.logic_resolve import all_public_logic_names

    # Package surface + brain modules (three-brains: optimizer not only on import logic)
    return all_public_logic_names()


def _collect_from_ast(path: str) -> Set[str]:
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "logic":
            for alias in node.names:
                if alias.name != "*":
                    names.add(alias.name)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "logic":
                names.add(node.attr)
    return names


def _collect_from_regex(path: str) -> Set[str]:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    names: Set[str] = set()
    for block in re.findall(r"from\s+logic\s+import\s+\((.*?)\)", text, re.S):
        for part in block.split(","):
            token = part.strip().split("#")[0].strip()
            if not token:
                continue
            names.add(token.split(" as ")[0].strip())
    for block in re.findall(r"from\s+logic\s+import\s+([^\n#]+)", text):
        if "(" in block:
            continue
        for part in block.split(","):
            token = part.strip()
            if token:
                names.add(token.split(" as ")[0].strip())
    for match in re.findall(r"\blogic\.([a-zA-Z_][a-zA-Z0-9_]*)", text):
        if match != "py":
            names.add(match)
    return names


def _iter_py_files() -> Iterable[str]:
    for entry in SCAN_DIRS:
        path = os.path.join(ROOT, entry)
        if os.path.isfile(path):
            yield path
            continue
        for dirpath, _dirnames, filenames in os.walk(path):
            for fname in filenames:
                if not fname.endswith(".py") or fname in SKIP_FILES:
                    continue
                yield os.path.join(dirpath, fname)


def collect_imported_symbols() -> Dict[str, Set[str]]:
    by_file: Dict[str, Set[str]] = {}
    for path in _iter_py_files():
        symbols = _collect_from_ast(path) | _collect_from_regex(path)
        if symbols:
            by_file[os.path.relpath(path, ROOT)] = symbols
    return by_file


def audit_logic_imports() -> Tuple[List[str], Dict[str, Set[str]]]:
    exports = _logic_exports()
    by_file = collect_imported_symbols()
    all_imported: Set[str] = set()
    for symbols in by_file.values():
        all_imported |= symbols
    missing = sorted(name for name in (all_imported - exports) if not name.startswith("_"))
    return missing, by_file


def run_audit(verbose: bool = False) -> int:
    missing, by_file = audit_logic_imports()
    print("Logic import audit")
    print("=" * 60)
    if missing:
        print(f"  [FAIL] {len(missing)} missing export(s):")
        for name in missing:
            refs = [rel for rel, syms in sorted(by_file.items()) if name in syms]
            print(f"    - {name}")
            if verbose:
                for ref in refs:
                    print(f"        used in {ref}")
    else:
        print("  [PASS] all imported logic symbols resolve")
    print("=" * 60)
    return 1 if missing else 0


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    raise SystemExit(run_audit(verbose=verbose))
