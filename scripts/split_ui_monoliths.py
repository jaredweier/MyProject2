"""Split ui/feature_pages.py and ui/schedule_pages.py into slice modules."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "ui"


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"  wrote {path.relative_to(ROOT)} ({len(text.splitlines())} lines)")


def split_feature_pages() -> None:
    lines = (UI / "feature_pages.py").read_text(encoding="utf-8").splitlines()
    if len(lines) < 500:
        print("  feature_pages.py already split — skip")
        return
    shared_imports = "\n".join(lines[2:68]) + "\n\n"
    reports = "\n".join(lines[70:1011]) + "\n"
    availability = "\n".join(lines[1012:]) + "\n"

    _write(
        UI / "reports_pages.py",
        '"""Reports tab mixin — analytics dashboard and exports."""\n\n' + shared_imports + reports,
    )
    _write(
        UI / "availability_pages.py",
        '"""Availability tab mixin — blackout dates, holidays, open shifts."""\n\n' + shared_imports + availability,
    )
    _write(
        UI / "feature_pages.py",
        '"""Backward-compatible re-exports — prefer ui.reports_pages / ui.availability_pages."""\n\n'
        "from ui.availability_pages import AvailabilityPageMixin\n"
        "from ui.reports_pages import ReportsPageMixin\n\n"
        '__all__ = ["AvailabilityPageMixin", "ReportsPageMixin"]\n',
    )


def split_schedule_pages() -> None:
    lines = (UI / "schedule_pages.py").read_text(encoding="utf-8").splitlines()
    if len(lines) < 500:
        print("  schedule_pages.py already split — skip")
        return
    header = "\n".join(lines[0:58]) + "\n\n"
    gantt_methods = "\n".join(lines[59:344]) + "\n"
    gantt_methods = gantt_methods.replace("class SchedulePageMixin:", "class GanttPageMixin:", 1)
    monthly_methods = "\n".join(lines[345:]) + "\n"

    _write(
        UI / "gantt_pages.py",
        '"""Gantt / timeline tab mixin."""\n\n' + header + gantt_methods,
    )
    _write(
        UI / "monthly_schedule_pages.py",
        '"""Base and updated monthly schedule tab mixin."""\n\n'
        + header
        + "class MonthlySchedulePageMixin:\n"
        + monthly_methods,
    )
    _write(
        UI / "schedule_pages.py",
        '"""Backward-compatible re-exports — prefer ui.gantt_pages / ui.monthly_schedule_pages."""\n\n'
        "from ui.gantt_pages import GanttPageMixin\n"
        "from ui.monthly_schedule_pages import MonthlySchedulePageMixin\n\n\n"
        "class SchedulePageMixin(GanttPageMixin, MonthlySchedulePageMixin):\n"
        '    """Timeline + base/updated monthly schedules."""\n\n\n'
        '__all__ = ["GanttPageMixin", "MonthlySchedulePageMixin", "SchedulePageMixin"]\n',
    )


def main() -> int:
    print("Splitting UI monoliths...")
    split_feature_pages()
    split_schedule_pages()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
