"""
Virtual lab readiness pack — prove ship gates + UAT scenarios + how to host.

12-hour virtual test prep (LAN / remote browser / VM):
  1) doctor + readiness + residual + UAT scenarios
  2) optional ship check
  3) print human UAT card + start command (isolated lab DB)

Run:
  python dev.py virtual-lab
  python dev.py virtual-lab --ship
  python dev.py virtual-lab --scenarios-only
  python scripts/virtual_lab.py --print-card
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LAB_DB = ROOT / "lab_data" / "virtual_uat.db"
STATUS_PATH = ROOT / "logs" / "virtual_lab_status.json"


def _run(cmd: list[str], *, timeout: int = 600) -> tuple[int, str]:
    env = os.environ.copy()
    env.setdefault("SCHEDULER_SKIP_GATES", "1")
    try:
        r = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out
    except subprocess.TimeoutExpired as exc:
        return 1, f"timeout: {exc}"


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def print_uat_card(*, host: str = "127.0.0.1", port: int = 8080) -> None:
    url = f"http://{host}:{port}"
    print()
    print("=" * 64)
    print("CHRONOS COMMAND — VIRTUAL UAT CARD")
    print("=" * 64)
    print(f"URL:     {url}")
    print("Logins:  admin/admin · supervisor/supervisor · officer/officer")
    print("Doc:     docs/VIRTUAL_UAT.md")
    print()
    print("Entry criteria (must be green before humans click):")
    print("  · doctor + readiness-check + residual_proof + virtual UAT scenarios")
    print("  · ship claim: verify --tier check + honest_gate true")
    print()
    print("Human role paths (industry LE critical):")
    print("  Officer     My Week · Time Off submit · Open shifts · Shift exchange")
    print("  Supervisor  Ops Desk · Leave approve (plan pick) · Swaps · Callout")
    print("  Admin       Roster · Payroll lock awareness · Deploy · Security · Audit")
    print()
    print("Honest residuals (do NOT fail UAT on these):")
    print("  · Live carrier SMS/email — file sink only (deferred)")
    print("  · LDAP production_ready — needs real AD + IT sign-off")
    print("  · Approve leave offline — intentional supervisor safety block")
    print()
    print("Start server (isolated lab DB recommended):")
    print('  $env:SCHEDULER_SKIP_GATES="1"')
    print(f'  $env:SCHEDULER_DB_PATH="{LAB_DB}"')
    print(f"  python main.py --browser --host 0.0.0.0 --port {port}")
    print("  # or: scripts\\host_online.bat  (uses default DB)")
    print()
    print("Automated browser (ONE Chronos only on :8080):")
    print("  python dev.py chronos-e2e --quick")
    print("  python dev.py chronos-e2e")
    print()
    print("Reset lab DB: delete lab_data\\virtual_uat.db then restart.")
    print("=" * 64)


def run_virtual_lab(
    *,
    ship: bool = False,
    scenarios_only: bool = False,
    print_card: bool = True,
    skip_residual: bool = False,
) -> int:
    print("Chronos Command — virtual lab readiness")
    print("=" * 60)
    results: dict[str, Any] = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "steps": {},
        "ready": False,
        "honest_ship": False,
    }
    failed: list[str] = []

    if scenarios_only:
        code, out = _run([sys.executable, str(ROOT / "scripts" / "virtual_uat_scenarios.py")], timeout=180)
        print(out[-4000:] if len(out) > 4000 else out)
        results["steps"]["scenarios"] = {"code": code}
        if code != 0:
            failed.append("scenarios")
        results["ready"] = code == 0
        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATUS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
        if print_card:
            print_uat_card()
        return 0 if not failed else 1

    steps = [
        ("doctor", [sys.executable, "dev.py", "doctor"], 120),
        ("readiness", [sys.executable, "scripts/readiness_check.py"], 180),
        ("scenarios", [sys.executable, "scripts/virtual_uat_scenarios.py"], 180),
    ]
    if not skip_residual:
        steps.append(("residual", [sys.executable, "scripts/residual_proof_smoke.py"], 300))
    if ship:
        steps.append(("verify_check", [sys.executable, "dev.py", "verify", "--tier", "check"], 900))

    for name, cmd, timeout in steps:
        print(f"\n>>> {name}", flush=True)
        code, out = _run(cmd, timeout=timeout)
        tail = out[-2500:] if len(out) > 2500 else out
        print(tail)
        results["steps"][name] = {"code": code}
        if code != 0:
            failed.append(name)
            print(f"[FAIL] {name} exit={code}")
        else:
            print(f"[ok] {name}")

    # Live server probe (optional info)
    live = _port_open("127.0.0.1", 8080)
    results["server_8080"] = live
    print(f"\n[info] :8080 {'UP — can run chronos-e2e --quick' if live else 'down — start main.py --browser'}")

    if ship and "verify_check" in results["steps"] and results["steps"]["verify_check"]["code"] == 0:
        try:
            last = json.loads((ROOT / "logs" / "last_verify.json").read_text(encoding="utf-8"))
            results["honest_ship"] = bool(last.get("honest_gate"))
            results["last_verify"] = {
                "honest_gate": last.get("honest_gate"),
                "passed": last.get("passed", last.get("ok")),
                "tier": last.get("tier") or last.get("mode"),
            }
        except Exception as exc:
            results["honest_ship"] = False
            results["last_verify_error"] = str(exc)

    results["ready"] = not failed
    results["failed"] = failed
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")

    if print_card:
        print_uat_card()

    print()
    if failed:
        print(f"virtual-lab: NOT READY — failed: {', '.join(failed)}")
        print(f"status → {STATUS_PATH}")
        return 1
    ship_note = ""
    if ship:
        ship_note = " · honest_ship=" + str(results.get("honest_ship"))
    print(f"virtual-lab: READY for virtual UAT{ship_note}")
    print(f"status → {STATUS_PATH}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Virtual lab readiness for Chronos UAT")
    p.add_argument("--ship", action="store_true", help="Also run verify --tier check")
    p.add_argument("--scenarios-only", action="store_true", help="Only LE UAT scenario smoke")
    p.add_argument("--print-card", action="store_true", help="Only print human UAT card")
    p.add_argument("--skip-residual", action="store_true", help="Skip residual_proof_smoke")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    args = p.parse_args(argv)
    if args.print_card and not args.ship and not args.scenarios_only:
        # print-card alone
        if len(sys.argv) <= 2 or (len(sys.argv) == 2 and "--print-card" in sys.argv):
            print_uat_card(host=args.host, port=args.port)
            return 0
    return run_virtual_lab(
        ship=args.ship,
        scenarios_only=args.scenarios_only,
        print_card=True,
        skip_residual=args.skip_residual,
    )


if __name__ == "__main__":
    raise SystemExit(main())
