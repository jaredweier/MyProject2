"""Vertical slice map and integrity checks."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from slices.registry import SHARED_KERNEL, SLICES  # noqa: E402


def _logic_has(name: str) -> bool:
    import database
    import logic

    if "." in name:
        mod_name, attr = name.split(".", 1)
        mod = database if mod_name == "database" else logic
        return hasattr(mod, attr)
    return hasattr(logic, name)


def _validator_has(name: str) -> bool:
    import validators

    return hasattr(validators, name)


def _page_keys() -> set:
    from ui.theme import NAV_ITEMS

    return {key for key, _label, _icon in NAV_ITEMS}


def run_slice_map(verbose: bool = False) -> int:
    pages = _page_keys()
    print("Dodgeville PD Scheduler — vertical slice map")
    print("=" * 78)
    print(f"{'Slice':<22} {'Status':<10} {'UI':<4} {'Logic':<6} {'Tests':<6} Future module")
    print("-" * 78)

    for s in SLICES:
        ui_ok = all(p in pages for p in s.get("ui_pages", []))
        logic_syms = list(s.get("logic", [])) + list(s.get("logic_extra", []))
        logic_ok = all(_logic_has(fn) for fn in logic_syms) if logic_syms else True
        tests = s.get("tests", [])
        tests_ok = all(os.path.isfile(os.path.join(ROOT, t.replace("/", os.sep))) for t in tests) if tests else True
        mark_u = "✓" if ui_ok else "—"
        mark_l = "✓" if logic_ok else "—"
        mark_t = "✓" if tests_ok else "—"
        print(
            f"{s['id']:<22} {s.get('status', '?'):<10} {mark_u:<4} {mark_l:<6} {mark_t:<6} {s.get('future_module', '')}"
        )
        if verbose:
            print(f"    {s.get('summary', '')}")
            if s.get("touch_together"):
                print(f"    touch: {', '.join(s['touch_together'][:5])}{'…' if len(s['touch_together']) > 5 else ''}")

    print("-" * 78)
    print(f"Shared kernel files: {len(SHARED_KERNEL['files'])}")
    print(f"Slices registered: {len(SLICES)}")
    return 0


def run_slice_check(strict: bool = False) -> int:
    import permissions

    pages = _page_keys()
    perm_keys = set(permissions.PERMISSIONS.keys())
    issues: List[str] = []
    warnings: List[str] = []

    for s in SLICES:
        sid = s["id"]
        for page in s.get("ui_pages", []):
            if page not in pages:
                issues.append(f"{sid}: unknown ui page '{page}'")
        mixin = s.get("ui_mixin", "")
        if mixin and not os.path.isfile(os.path.join(ROOT, mixin.replace("/", os.sep))):
            issues.append(f"{sid}: missing ui mixin {mixin}")
        for fn in s.get("logic", []):
            if not _logic_has(fn):
                issues.append(f"{sid}: missing logic.{fn}")
        for fn in s.get("logic_extra", []):
            if not _logic_has(fn):
                issues.append(f"{sid}: missing {fn}")
        for fn in s.get("validators", []):
            if fn and not _validator_has(fn):
                issues.append(f"{sid}: missing validators.{fn}")
        for perm in s.get("permissions", []):
            if perm not in perm_keys:
                warnings.append(f"{sid}: permission '{perm}' not in permissions.PERMISSIONS")
        for path in s.get("tests", []):
            if not os.path.isfile(os.path.join(ROOT, path.replace("/", os.sep))):
                issues.append(f"{sid}: missing test file {path}")
        for path in s.get("touch_together", []):
            if not os.path.isfile(os.path.join(ROOT, path.replace("/", os.sep))):
                issues.append(f"{sid}: touch_together file missing {path}")
        if s.get("status") == "planned":
            warnings.append(f"{sid}: slice marked planned")

    for path in SHARED_KERNEL["files"]:
        if not os.path.isfile(os.path.join(ROOT, path.replace("/", os.sep))):
            issues.append(f"shared_kernel: missing {path}")

    print("Vertical slice check")
    print("=" * 60)
    if issues:
        print(f"Issues ({len(issues)}):")
        for item in issues:
            print(f"  [FAIL] {item}")
    else:
        print("  All slice bindings resolve.")
    if warnings:
        print(f"Warnings ({len(warnings)}):")
        for item in warnings:
            print(f"  [WARN] {item}")

    if issues:
        return 1
    if strict and warnings:
        return 1
    return 0


def _find_slice(slice_id: str) -> Optional[dict]:
    needle = slice_id.strip().lower()
    for s in SLICES:
        if s["id"].lower() == needle:
            return s
    return None


def run_verify_slice(slice_id: str) -> int:
    """Run verify commands registered for a single vertical slice."""
    match = _find_slice(slice_id)
    if not match:
        ids = ", ".join(s["id"] for s in SLICES)
        print(f"Unknown slice '{slice_id}'. Registered: {ids}")
        return 1

    steps = list(match.get("verify", []))
    if not steps:
        print(f"Slice '{match['id']}' has no verify commands in slices/registry.py")
        return 1

    dev_py = os.path.join(ROOT, "dev.py")
    print(f"Verify slice: {match['id']} — {match.get('name', '')}")
    print("=" * 60)
    failed: List[str] = []
    for name in steps:
        print(f"\n>>> {name}", flush=True)
        result = subprocess.run(
            [sys.executable, dev_py, name],
            cwd=ROOT,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            failed.append(name)

    print("\n" + "=" * 60)
    if failed:
        print(f"verify-slice {match['id']}: FAILED — {', '.join(failed)}")
        return 1
    print(f"verify-slice {match['id']}: ALL PASSED")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["map", "check", "verify"], nargs="?", default="map")
    parser.add_argument("slice_id", nargs="?", help="Slice id for verify command")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.command == "check":
        raise SystemExit(run_slice_check(strict=args.strict))
    if args.command == "verify":
        if not args.slice_id:
            print("Usage: python scripts/vertical_slices.py verify <slice-id>")
            raise SystemExit(1)
        raise SystemExit(run_verify_slice(args.slice_id))
    raise SystemExit(run_slice_map(verbose=args.verbose))
