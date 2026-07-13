"""CLI handlers — bid cmds."""

from __future__ import annotations

from logic import (
    create_shift_bid_event,
    create_shift_bid_from_simulation,
    finalize_shift_bid_event,
    format_bid_event_summary,
    get_shift_bid_event,
    get_shift_bid_events,
    get_shift_bid_participation_report,
    get_shift_bid_rankings_for_event,
    load_simulator_scenario_for_bid,
    preview_shift_bid_awards,
    publish_shift_bid_event,
    reassign_shift_bid_option,
    submit_shift_bid_rankings,
    update_shift_bid_assignments,
)


def list_shift_bids_cmd(args):
    if args.officer_id:
        events = get_shift_bid_events(officer_id=args.officer_id)
    else:
        events = get_shift_bid_events(include_drafts=True)
    if not events:
        print("No shift bid events.")
        return
    for ev in events:
        squad = f"Squad {ev['squad']} " if ev.get("squad") else ""
        print(
            f"{ev['id']:<4} [{ev['status']:<10}] {ev.get('title') or 'Shift Bid':<24} {squad}"
            f"due {ev.get('bids_due_by') or '—'}  ({ev.get('respondent_count', 0)} responses)"
        )


def post_shift_bid_event_cmd(args):
    result = create_shift_bid_event(
        title=args.title or "Shift Bid",
        number_of_shifts=args.number_of_shifts or "",
        shift_length=args.shift_length or "",
        rotation=args.rotation or "",
        shift_start_times=args.shift_start_times or "",
        shifts_begin=args.shifts_begin or "",
        bids_due_by=args.bids_due_by or "",
        squad=args.squad,
        notes=args.notes or "",
    )
    if not result.get("success"):
        print(f"Error: {result.get('message')}")
        return
    event_id = result["event_id"]
    if args.publish:
        pub = publish_shift_bid_event(event_id)
        if not pub.get("success"):
            print(f"Created draft {event_id} but publish failed: {pub.get('message')}")
            return
        print(f"Shift bid published (ID: {event_id}, {pub.get('option_count', 0)} shifts)")
    else:
        print(f"Shift bid draft created (ID: {event_id})")


def submit_shift_bid_cmd(args):
    rankings = []
    for rank_str in args.rankings:
        if ":" not in rank_str:
            print(f"Invalid ranking '{rank_str}' — use option_id:rank")
            return
        opt_s, rank_s = rank_str.split(":", 1)
        rankings.append({"option_id": int(opt_s), "preference_rank": int(rank_s)})
    result = submit_shift_bid_rankings(args.event_id, args.officer_id, rankings)
    if result.get("success"):
        print(f"Rankings submitted ({result.get('ranked_count', 0)} preferences)")
    else:
        print(f"Error: {result.get('message')}")


def reassign_shift_bid_cmd(args):
    officer_id = None if args.clear else args.officer_id
    if not args.clear and officer_id is None:
        print("Error: provide --officer-id or --clear")
        return
    result = reassign_shift_bid_option(args.event_id, args.option_id, officer_id)
    if result.get("success"):
        print(f"Updated {result.get('changed', 0)} assignment(s)")
    else:
        print(f"Error: {result.get('message')}")


def finalize_shift_bid_cmd(args):
    result = finalize_shift_bid_event(args.event_id)
    if result.get("success"):
        for award in result.get("awards", []):
            print(f"  {award['officer_name']} -> {award['option_label']}")
        print(f"Finalized ({result.get('award_count', 0)} awards)")
    else:
        print(f"Error: {result.get('message')}")


def show_shift_bid_cmd(args):
    print(format_bid_event_summary(args.event_id))
    event = get_shift_bid_event(args.event_id)
    if event and event.get("options"):
        print("\nShifts:")
        for opt in event["options"]:
            awarded = f" -> {opt.get('awarded_officer_name')}" if opt.get("awarded_officer_id") else ""
            print(f"  {opt['id']}: {opt['label']} [{opt['status']}]{awarded}")
    rankings = get_shift_bid_rankings_for_event(args.event_id)
    if rankings:
        print("\nRankings:")
        for row in rankings:
            print(
                f"  {row['officer_name']:<22} {row['option_label']:<10} "
                f"pref #{row['preference_rank']}  seniority {row['seniority_rank']}"
            )


def preview_shift_bid_cmd(args):
    result = preview_shift_bid_awards(args.event_id)
    if not result.get("success"):
        print(f"Error: {result.get('message')}")
        return
    for award in result.get("awards", []):
        print(f"  {award['officer_name']} -> {award['option_label']} (pref #{award['preference_rank']})")
    for opt in result.get("unassigned_options", []):
        print(f"  Unassigned: {opt.get('label')}")
    print(f"Preview: {result.get('award_count', 0)} award(s)")


def participation_shift_bid_cmd(args):
    report = get_shift_bid_participation_report(args.event_id)
    if not report.get("success"):
        print(f"Error: {report.get('message')}")
        return
    print(f"{report.get('title') or 'Shift Bid'} [{report.get('status')}]")
    print(f"Eligible: {report.get('eligible_count', 0)}  Responded: {report.get('respondent_count', 0)}")
    missing = report.get("missing_officers") or []
    if missing:
        print("No response:")
        for row in missing:
            print(f"  {row['name']}")


def assignments_shift_bid_cmd(args):
    assignments = []
    for spec in args.assignments:
        if ":" not in spec:
            print(f"Invalid assignment '{spec}' — use option_id:officer_id or option_id:none")
            return
        opt_s, off_s = spec.split(":", 1)
        officer_id = None if off_s.lower() in ("none", "clear", "0") else int(off_s)
        assignments.append({"option_id": int(opt_s), "officer_id": officer_id})
    result = update_shift_bid_assignments(args.event_id, assignments)
    if result.get("success"):
        print(f"Updated {result.get('changed', 0)} assignment(s)")
    else:
        print(f"Error: {result.get('message')}")


def import_sim_shift_bid_cmd(args):
    if args.scenario_id:
        sim = load_simulator_scenario_for_bid(args.scenario_id)
    else:
        from logic import run_schedule_simulation

        sim = run_schedule_simulation(
            args.rotation or "4-on-4-off",
            args.officers or 8,
            args.shift_length or 10.0,
            args.annual_hours or 2080.0,
            [s.strip() for s in (args.shift_starts or "06:00,16:00").split(",") if s.strip()],
            apply_department_rules=False,
            min_per_shift=1,
        )
    if not sim.get("success"):
        print(f"Error: {sim.get('message', 'Simulation failed')}")
        return
    result = create_shift_bid_from_simulation(
        sim,
        publish=args.publish,
        title=args.title,
        squad=args.squad,
        bids_due_by=args.bids_due_by or "",
        shifts_begin=args.shifts_begin or "",
    )
    if result.get("success"):
        print(f"Shift bid created (ID: {result['event_id']})" + (" and published" if args.publish else ""))
    else:
        print(f"Error: {result.get('message')}")
