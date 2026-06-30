"""
Unified UI observation — capture runtime + static review for agent vision workflows.

Run:
  python dev.py ui-observe              # smoke + static review + brief
  python dev.py ui-observe --live       # screenshots first, then smoke + review
  python dev.py ui-observe --static-only
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _latest_dir(parent: str) -> str:
    if not os.path.isdir(parent):
        return ""
    runs = [
        os.path.join(parent, name)
        for name in os.listdir(parent)
        if os.path.isdir(os.path.join(parent, name)) and not name.startswith(".")
    ]
    if not runs:
        return ""
    runs.sort(key=os.path.getmtime, reverse=True)
    return runs[0]


def _list_pngs(directory: str) -> list[str]:
    if not directory or not os.path.isdir(directory):
        return []
    return sorted(os.path.join(directory, name) for name in os.listdir(directory) if name.lower().endswith(".png"))


def _read_review_summary(report_json: str) -> dict:
    if not os.path.isfile(report_json):
        return {}
    with open(report_json, encoding="utf-8") as fh:
        data = json.load(fh)
    findings = data.get("findings", [])
    summary = {"error": 0, "warn": 0, "info": 0}
    for item in findings:
        sev = item.get("severity", "info")
        summary[sev] = summary.get(sev, 0) + 1
    return {
        "summary": summary,
        "total": len(findings),
        "top": findings[:12],
    }


def run_ui_observe(
    *,
    live: bool = False,
    static_only: bool = False,
    skip_smoke: bool = False,
    live_delay: float = 0.5,
    live_hold: float = 4.0,
    verbose: bool = False,
) -> int:
    from paths import data_path

    dev_py = os.path.join(ROOT, "dev.py")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    bundle_dir = data_path(os.path.join("logs", "ui_observe", stamp))
    os.makedirs(bundle_dir, exist_ok=True)

    print("Dodgeville PD Scheduler — UI observe")
    print("=" * 60)
    print(f"Bundle: {bundle_dir}")

    failed: list[str] = []
    screenshot_dir = _latest_dir(data_path(os.path.join("logs", "ui_live_test")))

    if live and not static_only:
        print("\n>>> ui-live (screenshots)", flush=True)
        result = subprocess.run(
            [
                sys.executable,
                dev_py,
                "ui-live",
                "--delay",
                str(live_delay),
                "--hold",
                str(live_hold),
            ],
            cwd=ROOT,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            failed.append("ui-live")
        screenshot_dir = _latest_dir(data_path(os.path.join("logs", "ui_live_test"))) or screenshot_dir

    if not static_only and not skip_smoke:
        print("\n>>> ui-smoke", flush=True)
        result = subprocess.run(
            [sys.executable, dev_py, "ui-smoke"],
            cwd=ROOT,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            failed.append("ui-smoke")

    print("\n>>> ui-review", flush=True)
    review_args = [sys.executable, dev_py, "ui-review"]
    if verbose:
        review_args.append("-v")
    result = subprocess.run(review_args, cwd=ROOT, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        failed.append("ui-review")

    review_dir = _latest_dir(data_path(os.path.join("logs", "ui_review")))
    review_json = os.path.join(review_dir, "report.json") if review_dir else ""
    review_md = os.path.join(review_dir, "report.md") if review_dir else ""
    screenshots = _list_pngs(screenshot_dir)
    review_data = _read_review_summary(review_json)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bundle_dir": bundle_dir,
        "screenshot_dir": screenshot_dir,
        "screenshot_count": len(screenshots),
        "screenshots": screenshots,
        "review_dir": review_dir,
        "review_json": review_json,
        "review_md": review_md,
        "review_summary": review_data.get("summary", {}),
        "failed_steps": failed,
        "agent_skill": ".grok/skills/ui-vision-review/SKILL.md",
    }
    manifest_path = os.path.join(bundle_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    brief_lines = [
        "# UI Observation Brief",
        "",
        f"Generated: {manifest['generated_at']}",
        "",
        "## For agents (vision + fixes)",
        "",
        "1. Read this brief and `manifest.json`",
        "2. Load **UI vision review** skill: `.grok/skills/ui-vision-review/SKILL.md`",
        "3. Read PNGs listed below (layout, contrast, density, LE theme)",
        "4. Read static report: `review_md`",
        "5. Apply fixes via `ui-development` + `ui-aesthetics-review` skills",
        "6. Re-run: `python dev.py ui-observe`",
        "",
        "## Screenshots",
        "",
    ]
    if screenshot_dir:
        brief_lines.append(f"Directory: `{screenshot_dir}` ({len(screenshots)} PNGs)")
        brief_lines.append("")
        for path in screenshots[:20]:
            brief_lines.append(f"- `{path}`")
        if len(screenshots) > 20:
            brief_lines.append(f"- … and {len(screenshots) - 20} more")
    else:
        brief_lines.append("No screenshots yet. Run: `python dev.py ui-observe --live`")

    brief_lines.extend(
        [
            "",
            "## Static review",
            "",
        ]
    )
    if review_md:
        brief_lines.append(f"Report: `{review_md}`")
        sm = review_data.get("summary", {})
        brief_lines.append(
            f"Findings: {review_data.get('total', 0)} "
            f"(errors={sm.get('error', 0)}, warnings={sm.get('warn', 0)}, info={sm.get('info', 0)})",
        )
        for item in review_data.get("top", []):
            loc = item.get("file", "")
            if item.get("line"):
                loc = f"{loc}:{item['line']}"
            brief_lines.append(
                f"- [{item.get('severity', '?')}] {item.get('message', '')} (`{loc}`)",
            )
    else:
        brief_lines.append("No ui-review report found.")

    brief_lines.extend(
        [
            "",
            "## Runtime",
            "",
            f"Failed steps: {', '.join(failed) if failed else 'none'}",
            "",
            "## Key tabs to inspect visually",
            "",
            "- Login / Command Post (dashboard)",
            "- Original + Current Monthly Schedule",
            "- Timecard, Duty Timeline (Gantt)",
            "- Time Off, Shift Exchange",
            "- Patrol Roster, Payroll Ledger",
            "- Ops Reports, Access Control",
            "",
        ]
    )

    brief_path = os.path.join(bundle_dir, "observation_brief.md")
    with open(brief_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(brief_lines))

    print("\n" + "=" * 60)
    print(f"Observation brief: {brief_path}")
    print(f"Manifest: {manifest_path}")
    if screenshot_dir:
        print(f"Screenshots: {screenshot_dir} ({len(screenshots)} files)")
    if review_dir:
        print(f"Static review: {review_dir}")
    if failed:
        print(f"ui-observe: PARTIAL — failed: {', '.join(failed)}")
        return 1
    print("ui-observe: ALL PASSED")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Unified UI observation bundle for agents")
    parser.add_argument("--live", action="store_true", help="Run ui-live screenshots first")
    parser.add_argument("--static-only", action="store_true", help="Skip ui-smoke; ui-review only")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip ui-smoke")
    parser.add_argument("--delay", type=float, default=0.5, help="ui-live step delay")
    parser.add_argument("--hold", type=float, default=4.0, help="ui-live hold at end")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose ui-review")
    args = parser.parse_args()
    raise SystemExit(
        run_ui_observe(
            live=args.live,
            static_only=args.static_only,
            skip_smoke=args.skip_smoke,
            live_delay=args.delay,
            live_hold=args.hold,
            verbose=args.verbose,
        )
    )
