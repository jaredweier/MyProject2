"""
Chronos parity audit — free local CPU, $0 LLM.

Compares logic symbols (from slice registry) to actual references in gui/ and cli.py.
Surfaces “logic strong / UI thin” without agent theater.

    python dev.py parity-audit
    python dev.py parity-audit --json
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class SymbolHit:
    name: str
    in_gui: bool
    in_cli: bool
    gui_files: List[str]
    slice_id: str


def _read_sources() -> Dict[str, str]:
    texts: Dict[str, str] = {}
    for base in (ROOT / "gui",):
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            texts[rel] = path.read_text(encoding="utf-8", errors="replace")
    cli = ROOT / "cli.py"
    if cli.is_file():
        texts["cli.py"] = cli.read_text(encoding="utf-8", errors="replace")
    return texts


def _symbol_used(name: str, text: str) -> bool:
    # word-boundary-ish: name( or name,
    return bool(re.search(rf"\b{re.escape(name)}\b", text))


def collect_hits() -> List[SymbolHit]:
    from slices.registry import SLICES

    sources = _read_sources()
    hits: List[SymbolHit] = []
    seen = set()
    for s in SLICES:
        for name in s.get("logic", []) + s.get("logic_extra", []):
            short = name.split(".")[-1]
            if short in seen:
                continue
            seen.add(short)
            gui_files = []
            in_cli = False
            for rel, text in sources.items():
                if not _symbol_used(short, text):
                    continue
                if rel == "cli.py":
                    in_cli = True
                else:
                    gui_files.append(rel)
            hits.append(
                SymbolHit(
                    name=short,
                    in_gui=bool(gui_files),
                    in_cli=in_cli,
                    gui_files=gui_files,
                    slice_id=s["id"],
                )
            )
    return hits


def run_parity_audit(*, as_json: bool = False) -> int:
    hits = collect_hits()
    thin = [h for h in hits if not h.in_gui]
    wired = [h for h in hits if h.in_gui]
    if as_json:
        print(
            json.dumps(
                {
                    "total": len(hits),
                    "in_gui": len(wired),
                    "logic_only": len(thin),
                    "thin": [asdict(h) for h in thin],
                },
                separators=(",", ":"),
            )
        )
        return 0

    print("Dodgeville PD — Chronos parity audit (logic vs gui/)")
    print("=" * 72)
    print(f"Logic symbols scanned: {len(hits)}")
    print(f"  Referenced in gui/:  {len(wired)}")
    print(f"  Logic-only (thin):   {len(thin)}")
    print("-" * 72)
    print("Thin / missing Chronos wiring (top opportunities):")
    # Group by slice
    by_slice: Dict[str, List[str]] = {}
    for h in thin:
        by_slice.setdefault(h.slice_id, []).append(h.name)
    for sid, names in sorted(by_slice.items(), key=lambda kv: -len(kv[1])):
        print(f"  [{sid}] ({len(names)})")
        for n in names[:12]:
            print(f"      - {n}")
        if len(names) > 12:
            print(f"      … +{len(names) - 12} more")
    print("-" * 72)
    print("Wired examples (sample):")
    for h in wired[:8]:
        print(f"  + {h.name} → {', '.join(h.gui_files[:2])}")
    print("=" * 72)
    print("Use: prioritize gui/pages for thin slices · docs/EXTERNAL_TOOL_STACK.md")
    print("Machine next: python dev.py le-benchmark · python dev.py fuzz-scheduling")
    # Exit 0 always — report is informational (not a ship gate)
    return 0


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    raise SystemExit(run_parity_audit(as_json=a.json))
