"""CLI handlers — report cmds."""

from __future__ import annotations

from logic import (
    get_coverage_report,
    get_current_cycle_window,
    get_dashboard_insights,
    get_labor_compliance_report,
)
from validators import parse_date


def reports_labor_compliance(args):
    report = get_labor_compliance_report(officer_id=args.officer_id)
    scope = f" (officer {args.officer_id})" if args.officer_id else ""
    print(f"Labor compliance{scope}")
    print(
        f"§207(k) {report.get('flsa_207k_period_days')}-day period "
        f"{report.get('flsa_207k_period_start')} – {report.get('flsa_207k_period_end')} "
        f"(threshold {report.get('flsa_207k_threshold')}h, rotation {report.get('rotation_cycle_length')}d)"
    )
    print(
        f"Comp cap: {report.get('comp_cap_hours')}h  |  Max consecutive days: {report.get('max_consecutive_work_days')}"
    )
    print(f"Issues: {report.get('issue_count', 0)}")
    for item in report.get("issues", []):
        print(f"  [{item.get('severity', '?').upper()}] {item['officer_name']}: {item['message']}")


def reports_summary(args):
    insights = get_dashboard_insights(officer_id=args.officer_id)
    scope = f" (officer {args.officer_id})" if args.officer_id else ""
    print(f"Dashboard summary{scope}")
    print(f"Coverage issues (cycle): {insights.get('coverage_issues', 0)}")
    print(f"Overtime alerts: {insights.get('overtime_alerts', 0)}")
    print(f"Schedule conflicts: {insights.get('schedule_conflicts', 0)}")
    print(f"Schedule changes (month): {insights.get('schedule_diff_count', 0)}")
    print(f"Pending requests: {insights.get('pending_requests', 0)}")
    print(f"Pending swaps: {insights.get('pending_swaps', 0)}")
    print(f"Labor compliance issues: {insights.get('labor_compliance_count', 0)}")
    if insights.get("officer_scoped"):
        print(f"Pending manual review: {insights.get('pending_manual_review', 0)}")
        print(f"Claimable open shifts: {insights.get('claimable_open_shifts', 0)}")
    else:
        print(f"Open shifts posted: {insights.get('open_shifts', 0)}")
        print(f"Monthly labor (proj.): ${insights.get('monthly_labor_cost', 0):,.0f}")
        budget = insights.get("labor_budget") or {}
        if budget.get("configured"):
            print(
                f"Labor budget YTD: ${budget['ytd_spent']:,.0f} / ${budget['annual_budget']:,.0f} "
                f"({budget['ytd_pct']:.0f}%)"
            )


def reports_coverage(args):
    if args.start and args.end:
        start, end = parse_date(args.start), parse_date(args.end)
    else:
        start, end = get_current_cycle_window()
    report = get_coverage_report(start, end)
    print(f"Coverage {report['start_date']} – {report['end_date']}: {report['issue_count']} issue(s)")
    for issue in report.get("issues", []):
        print(f"  {issue['date']} Squad {issue['squad_on_duty']}: {issue['night_issues']}")
