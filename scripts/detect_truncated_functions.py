"""Detect logic.py functions that may be truncated (fall through to next def)."""

from __future__ import annotations

import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def detect_truncated(path: str) -> list[tuple[str, str]]:
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source)
    lines = source.splitlines()
    findings: list[tuple[str, str]] = []

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        body = node.body
        if not body:
            findings.append((node.name, "empty body"))
            continue
        last = body[-1]
        if isinstance(last, ast.Expr) and isinstance(last.value, ast.Constant):
            continue
        if isinstance(last, ast.Return):
            continue
        if isinstance(last, ast.Raise):
            continue
        if isinstance(last, ast.If) and last.orelse and isinstance(last.orelse[-1], ast.Return):
            continue
        next_line = lines[node.end_lineno - 1].strip() if node.end_lineno else ""
        if next_line.startswith("def ") or next_line.startswith("class "):
            findings.append((node.name, f"ends at line {node.end_lineno} without return"))
    return findings


def main() -> int:
    target = os.path.join(ROOT, "logic.py")
    findings = detect_truncated(target)
    print("Truncated function scan:", target)
    print("=" * 60)
    if not findings:
        print("  [PASS] no suspicious functions")
        return 0
    for name, detail in findings:
        print(f"  [WARN] {name}: {detail}")
    print("=" * 60)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
