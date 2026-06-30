"""AST outline of a Python file — minimal tokens vs full read."""

from __future__ import annotations

import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(ROOT, path)


def outline_file(path: str, *, max_items: int = 80) -> str:
    full = _resolve(path)
    if not os.path.isfile(full):
        return f"outline: file not found: {path}"

    with open(full, encoding="utf-8", errors="replace") as fh:
        source = fh.read()

    try:
        tree = ast.parse(source, filename=full)
    except SyntaxError as exc:
        return f"outline: syntax error in {path}: {exc}"

    rel = os.path.relpath(full, ROOT).replace("\\", "/")
    lines: list[str] = [f"# {rel} — AST outline (read full file only if editing a symbol below)"]
    count = 0

    for node in tree.body:
        if count >= max_items:
            lines.append("  ... (truncated — use outline --full or read file)")
            break
        if isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            m = ", ".join(methods[:12])
            if len(methods) > 12:
                m += ", ..."
            lines.append(f"  class {node.name}  L{node.lineno}" + (f"  [{m}]" if m else ""))
            count += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines.append(f"  def {node.name}()  L{node.lineno}")
            count += 1
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    lines.append(f"  {target.id} = ...  L{node.lineno}")
                    count += 1
                    break

    total_lines = source.count("\n") + (1 if source else 0)
    est = max(1, len(source) // 4)
    lines.append(f"# {total_lines} lines total, ~{est:,} tokens if read whole file")
    return "\n".join(lines)


def run_outline(path: str, *, full: bool = False) -> int:
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    print(outline_file(path, max_items=999 if full else 80))
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--full"]
    full = "--full" in sys.argv
    if not args:
        print("Usage: python scripts/file_outline.py <path>")
        raise SystemExit(1)
    raise SystemExit(run_outline(args[0], full=full))
