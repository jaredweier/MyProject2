"""Print UI ↔ logic ↔ CLI feature coverage map."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from slices.registry import features_for_map

FEATURES = features_for_map()


def run_feature_map() -> int:
    import database
    import logic
    import permissions

    print("Dodgeville PD Scheduler — feature map")
    print("=" * 72)
    print(f"{'Feature':<28} {'Logic':<6} {'UI':<4} {'CLI':<4} Permission")
    print("-" * 72)

    gaps = []
    for feat in FEATURES:
        logic_ok = all(hasattr(logic, fn) for fn in feat["logic"] if fn != "simulator module via ui")
        for fn in feat.get("extra", []):
            mod_name, _, attr = fn.partition(".")
            mod = database if mod_name == "database" else logic
            logic_ok = logic_ok and hasattr(mod, attr)
        ui_ok = bool(feat["ui"])
        cli_ok = bool(feat["cli"])
        mark_l = "✓" if logic_ok else "—"
        mark_u = "✓" if ui_ok else "—"
        mark_c = "✓" if cli_ok else "—"
        print(f"{feat['name']:<28} {mark_l:<6} {mark_u:<4} {mark_c:<4} {feat['perm']}")
        if not logic_ok:
            gaps.append(f"{feat['name']}: missing logic function(s)")
        if logic_ok and ui_ok and not cli_ok and feat["name"] not in ("Simulator",):
            gaps.append(f"{feat['name']}: no CLI surface (UI-only)")

    print("-" * 72)
    print(f"Roles: {', '.join(permissions.USER_ROLES)}")
    print(f"Permissions defined: {len(permissions.PERMISSIONS)}")
    if gaps:
        print("\nGaps / notes:")
        for g in gaps:
            print(f"  • {g}")
    else:
        print("\nNo coverage gaps detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_feature_map())
