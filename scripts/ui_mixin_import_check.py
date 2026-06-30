#!/usr/bin/env python3
"""Verify UI mixin modules define symbols they reference at runtime."""

from __future__ import annotations

import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(ROOT, "ui")

BUILTINS = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))
LOCAL_OK = {"ctk", "ctk", "True", "False", "None"}


def _collect_defs_and_imports(tree: ast.AST) -> tuple[set[str], set[str]]:
    imported: set[str] = set()
    defined: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.asname or alias.name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.add(alias.asname or alias.name)
        elif isinstance(node, ast.FunctionDef):
            defined.add(node.name)
        elif isinstance(node, ast.ClassDef):
            defined.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined.add(target.id)
    return imported, defined


def check_file(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    imported, defined = _collect_defs_and_imports(tree)
    known = imported | defined | BUILTINS | LOCAL_OK
    issues: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            name = node.id
            if name not in known and name[0].isupper():
                issues.append(f"{os.path.basename(path)}:{node.lineno}: undefined {name}")
                known.add(name)
    return issues


def main() -> int:
    all_issues: list[str] = []
    for name in sorted(os.listdir(UI)):
        if not name.endswith("_pages.py"):
            continue
        all_issues.extend(check_file(os.path.join(UI, name)))
    if all_issues:
        for item in all_issues:
            print(item)
        return 1
    print("ui mixin import check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
