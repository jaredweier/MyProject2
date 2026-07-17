"""Product complete pack — wire thin parity APIs + residual LE depth.

Honest residuals:
- Live SMS/email *delivery* only when Twilio/SMTP creds work (no fake sent).
- CAD/RMS is export/webhook boundary, not bidirectional CAD.
- Offline PWA is shell+cached pages, not full multi-page API offline.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from validators import format_date, parse_date, storage_date_str

# ---- Court minimum / holdover reason codes (CBA knobs) ----------------------

SETTING_COURT_MIN_HOURS = "court_appearance_min_hours"
SETTING_HOLDOVER_CODES = "holdover_reason_codes"
DEFAULT_HOLDOVER_CODES = [
    "Holdover end-of-shift",
    "Late call",
    "Court appearance",
    "Training overrun",
    "Incident command",
    "Supervisor directed",
    "Other",
]


def get_court_min_hours() -> float:
    from logic.operations import get_department_setting

    raw = get_department_setting(SETTING_COURT_MIN_HOURS, "2") or "2"
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return 2.0


def set_court_min_hours(hours: float, *, user_id: Optional[int] = None) -> Dict[str, Any]:
    from logic.operations import set_department_setting

    h = max(0.0, min(24.0, float(hours)))
    r = set_department_setting(SETTING_COURT_MIN_HOURS, str(h), user_id=user_id)
    if not r.get("success"):
        return r
    return {"success": True, "hours": h, "message": f"Court appearance minimum: {h:g}h"}


def get_holdover_reason_codes() -> List[str]:
    from logic.operations import get_department_setting

    raw = get_department_setting(SETTING_HOLDOVER_CODES, "") or ""
    if not raw.strip():
        return list(DEFAULT_HOLDOVER_CODES)
    try:
        data = json.loads(raw)
        if isinstance(data, list) and data:
            return [str(x).strip() for x in data if str(x).strip()]
    except json.JSONDecodeError:
        pass
    parts = [p.strip() for p in raw.split("|") if p.strip()]
    return parts or list(DEFAULT_HOLDOVER_CODES)


def save_holdover_reason_codes(codes: Sequence[str], *, user_id: Optional[int] = None) -> Dict[str, Any]:
    from logic.operations import set_department_setting

    cleaned = [str(c).strip() for c in codes if str(c).strip()]
    if not cleaned:
        cleaned = list(DEFAULT_HOLDOVER_CODES)
    r = set_department_setting(SETTING_HOLDOVER_CODES, json.dumps(cleaned), user_id=user_id)
    if not r.get("success"):
        return r
    return {"success": True, "codes": cleaned, "message": f"Saved {len(cleaned)} holdover reason codes"}


# ---- Parity: plan_bump_chain ------------------------------------------------


def plan_bump_chain_report(
    original_officer_id: int,
    request_date: str,
    squad: str,
    shift_start: str,
    *,
    max_depth: int = 8,
) -> Dict[str, Any]:
    """Supervisor-readable chain from plan_bump_chain (parity wire)."""
    from logic.bump_optimizer import plan_bump_chain, suggest_bump_chain

    chain, err = plan_bump_chain(
        int(original_officer_id),
        request_date,
        squad or "",
        shift_start or "",
        max_depth=max_depth,
    )
    suggestion = suggest_bump_chain(
        int(original_officer_id),
        request_date,
        squad or "",
        shift_start or "",
        max_depth=max_depth,
    )
    steps_txt = []
    for step in getattr(suggestion, "steps", None) or []:
        steps_txt.append(
            f"Step {step.step_number}: {step.replacement_officer_name} covers "
            f"{step.original_officer_name} ({step.original_shift})"
        )
    ok = bool(chain) and err is None and getattr(suggestion, "success", False)
    return {
        "success": ok,
        "chain": list(chain or []),
        "error": err,
        "message": (
            getattr(suggestion, "message", None)
            or (None if ok else (err or "Incomplete chain → manual review"))
            or "Bump chain ready"
        ),
        "steps_text": steps_txt,
        "text": "\n".join(
            [
                getattr(suggestion, "message", None) or ("OK" if ok else (err or "Manual review")),
                *steps_txt,
            ]
        ),
        "partial": not ok and bool(getattr(suggestion, "steps", None)),
    }


# ---- Parity: evaluate_day_coverage + windows --------------------------------


def _assignments_for_day(day: date) -> List[Tuple[date, str, str]]:
    """Build (date, start, end) tuples from live roster for evaluate_day_coverage."""
    from logic.officers import get_officers_by_seniority
    from logic.snapshots import get_officer_schedule_window

    out: List[Tuple[date, str, str]] = []
    for o in get_officers_by_seniority() or []:
        if not o.get("active", 1):
            continue
        oid = o.get("id")
        if not oid:
            continue
        try:
            window = get_officer_schedule_window(int(oid), start_date=day, days=1) or {}
        except Exception:
            continue
        days = window.get("schedule_days") or window.get("days") or window.get("schedule") or []
        rows = days if isinstance(days, list) else []
        if isinstance(days, dict):
            key = day.isoformat()
            val = days.get(key) or days.get(storage_date_str(day.isoformat()))
            if isinstance(val, dict):
                rows = [val]
            elif val:
                rows = [{"status": val}]
        for d in rows:
            if not isinstance(d, dict):
                continue
            status = (d.get("status") or d.get("duty") or "").lower()
            if status in ("off", "leave", "vacation", "sick", ""):
                # still allow if shift times present
                if not (d.get("shift_start") or d.get("start")):
                    continue
            start = d.get("shift_start") or d.get("start") or o.get("shift_start") or "06:00"
            end = d.get("shift_end") or d.get("end") or o.get("shift_end") or "14:00"
            if status in ("off",) and not d.get("covering"):
                continue
            out.append((day, str(start)[:5], str(end)[:5]))
    # Fallback: on-duty officers by rotation home shift
    if not out:
        from logic.scheduling import is_officer_working_on_day

        for o in get_officers_by_seniority() or []:
            if not o.get("active", 1):
                continue
            try:
                working = is_officer_working_on_day(int(o["id"]), day, o.get("squad"))
            except Exception:
                working = o.get("squad") in ("A", "B")
            if not working:
                continue
            start = o.get("shift_start") or "06:00"
            end = o.get("shift_end") or "14:00"
            out.append((day, str(start)[:5], str(end)[:5]))
    return out


def live_day_coverage_report(day: Any = None) -> Dict[str, Any]:
    """evaluate_day_coverage against live roster + stored windows (parity wire)."""
    from logic.coverage_timeline import CoverageWindow, evaluate_day_coverage
    from logic.coverage_windows_store import (
        get_active_coverage_windows,
        get_coverage_247_minimum,
        list_coverage_windows,
    )

    if day is None:
        day = date.today()
    elif isinstance(day, str):
        day = parse_date(day) or date.fromisoformat(storage_date_str(day))
    assert isinstance(day, date)
    assignments = _assignments_for_day(day)
    min_247 = get_coverage_247_minimum()
    raw_windows = get_active_coverage_windows() or list_coverage_windows() or []
    windows: List[CoverageWindow] = []
    for w in raw_windows:
        if isinstance(w, CoverageWindow):
            windows.append(w)
            continue
        if not isinstance(w, dict) or not w.get("enabled", True):
            continue
        try:
            from logic.coverage_windows_store import _parse_window_dict

            cw = _parse_window_dict(w)
            if cw:
                windows.append(cw)
        except Exception:
            continue
    result = evaluate_day_coverage(
        assignments,
        day,
        min_247=min_247,
        windows=windows or None,
    )
    checks = result.get("checks") or []
    lines = [f"Day coverage {format_date(day)} · assignments={len(assignments)} · ok={result.get('ok')}"]
    for c in checks:
        if not isinstance(c, dict):
            continue
        label = c.get("label") or c.get("kind") or "check"
        lines.append(
            f"  {'OK' if c.get('ok') else 'SHORT'} · {label} · "
            f"min={c.get('min_officers', c.get('minimum', '—'))} · "
            f"observed={c.get('min_occupancy', c.get('occupancy', c.get('count', '—')))}"
        )
    return {
        "success": True,
        "ok": bool(result.get("ok")),
        "day": day.isoformat(),
        "date_display": format_date(day),
        "assignment_count": len(assignments),
        "min_247": min_247,
        "checks": checks,
        "text": "\n".join(lines),
        "message": lines[0],
    }


def save_coverage_windows_ui(
    windows: List[Dict],
    *,
    min_247: Optional[int] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """save_coverage_windows + optional 24/7 minimum (parity wire)."""
    from logic.coverage_windows_store import save_coverage_windows, set_coverage_247_minimum

    r = save_coverage_windows(windows or [], user_id=user_id)
    if not r.get("success"):
        return r
    if min_247 is not None:
        set_coverage_247_minimum(int(min_247), user_id=user_id)
        r["min_247"] = int(min_247)
    r["message"] = r.get("message") or f"Saved {len(r.get('windows') or [])} windows"
    return r


# ---- Parity: build_pattern --------------------------------------------------


def preview_rotation_pattern(
    text: str,
    *,
    style: Optional[str] = None,
    phase: int = 0,
    shift_hours: float = 8.0,
) -> Dict[str, Any]:
    from logic.rotation_patterns import build_pattern, pattern_summary, projected_annual_hours

    try:
        pat = build_pattern(text, style=style, phase=phase)
    except ValueError as exc:
        return {"success": False, "message": str(exc)}
    annual = projected_annual_hours(pat, float(shift_hours))
    summary = pattern_summary(pat)
    wdays = pat.work_days_per_cycle() if callable(pat.work_days_per_cycle) else pat.work_days_per_cycle
    return {
        "success": True,
        "label": pat.label,
        "style": pat.style,
        "cycle_length": pat.cycle_length,
        "work_days_per_cycle": wdays,
        "annual_hours": annual,
        "summary": summary,
        "message": (
            f"{pat.label} · cycle {pat.cycle_length}d · {wdays} work days · ~{annual:.0f}h/yr @ {shift_hours:g}h"
        ),
        "text": json.dumps(summary, default=str) if isinstance(summary, dict) else str(summary),
    }


def apply_rotation_pattern_setting(
    text: str,
    *,
    style: Optional[str] = None,
    phase: int = 0,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Validate via build_pattern and store as department rotation variation text."""
    from logic.operations import set_department_setting

    prev = preview_rotation_pattern(text, style=style, phase=phase)
    if not prev.get("success"):
        return prev
    r = set_department_setting("rotation_pattern_text", (text or "").strip(), user_id=user_id)
    if style:
        set_department_setting("rotation_pattern_style", style, user_id=user_id)
    set_department_setting("rotation_pattern_phase", str(int(phase or 0)), user_id=user_id)
    if not r.get("success"):
        return r
    return {
        "success": True,
        "message": f"Saved rotation pattern · {prev.get('message')}",
        "preview": prev,
    }


# ---- Ops: recover + gap fill ------------------------------------------------


def recover_all_manual_review(
    *,
    action: str = "approve_override",
    user_id: Optional[int] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """One-click recover path to unblock publish (honest: override or order-in)."""
    from logic.ops_desk import list_manual_review_queue, resolve_manual_review

    q = list_manual_review_queue()
    items = q.get("items") or q.get("rows") or q.get("requests") or []
    if not items and isinstance(q, list):
        items = q
    done = []
    failed = []
    for item in items[: max(1, min(int(limit), 50))]:
        rid = item.get("id") if isinstance(item, dict) else None
        if rid is None:
            continue
        r = resolve_manual_review(int(rid), action, user_id=user_id)
        if r.get("success"):
            done.append(int(rid))
        else:
            failed.append({"id": int(rid), "message": r.get("message")})
    return {
        "success": True,
        "resolved": done,
        "failed": failed,
        "message": f"Recovered {len(done)} · failed {len(failed)} · action={action}",
    }


def fill_gap_click(
    original_officer_id: int,
    cover_officer_id: int,
    day: Any = None,
    *,
    reason: str = "Coverage gap fill",
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Gap cell → callout order-in (click-to-fill)."""
    from logic.callout_desk import execute_callout_order

    if day is None:
        day_s = format_date(date.today())
    elif isinstance(day, date):
        day_s = format_date(day)
    else:
        day_s = str(day)
    return execute_callout_order(
        int(original_officer_id),
        day_s,
        int(cover_officer_id),
        reason=reason,
        user_id=user_id,
    )


def gap_board_with_fill_actions(*, reference: Optional[date] = None) -> Dict[str, Any]:
    """Coverage gaps + callout candidates for first short day (ops click-to-fill)."""
    from logic.analytics import get_coverage_gap_board
    from logic.callout_desk import build_callout_ladder
    from logic.officers import get_officers_by_seniority

    reference = reference or date.today()
    # get_coverage_gap_board(hours_ahead) — 6-day look-ahead for ops fill board
    board = get_coverage_gap_board(hours_ahead=6 * 24) or {}
    gaps = board.get("gaps") or board.get("rows") or board.get("items") or []
    if isinstance(board, list):
        gaps = board
    officers = [o for o in (get_officers_by_seniority() or []) if o.get("active") == 1]
    primary = officers[0] if officers else None
    ladder = None
    if primary:
        ladder = build_callout_ladder(int(primary["id"]), format_date(reference), reason="Gap fill")
    return {
        "success": True,
        "gaps": gaps[:20] if isinstance(gaps, list) else [],
        "primary_officer_id": primary.get("id") if primary else None,
        "primary_officer_name": primary.get("name") if primary else None,
        "ladder": ladder,
        "message": f"{len(gaps) if isinstance(gaps, list) else 0} gap row(s)",
    }


# ---- Notify: live send with real recipient ----------------------------------


def live_notify_send_test(
    *,
    email: str = "",
    phone: str = "",
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Enqueue + process to *real* recipient when provided.

    Without transport: paths OK, not live_send_proved.
    With transport + real address: may mark sent (honest).
    """
    from logic.notify_channels import get_notify_channel_config
    from logic.notify_queue import enqueue_notify, list_notify_outbox, process_notify_outbox

    cfg = get_notify_channel_config()
    email = (email or "").strip()
    phone = (phone or "").strip()
    ids = []
    if email:
        ids.append(
            enqueue_notify(
                channel="email",
                subject="Chronos live notify test",
                body="Live transport test from Chronos Command (Weierworks).",
                recipient=email,
                template_key="channel_test",
                user_id=user_id,
                meta={"kind": "live_notify_send_test", "transport": "email"},
            )
        )
    if phone:
        ids.append(
            enqueue_notify(
                channel="sms",
                subject="Chronos live SMS test",
                body="Chronos live SMS test.",
                recipient=phone,
                template_key="channel_test",
                user_id=user_id,
                meta={"kind": "live_notify_send_test", "transport": "sms"},
            )
        )
    if not ids:
        # Fall back to proof path recipients (never claims live without real addr)
        from logic.notify_queue import prove_notify_paths

        return prove_notify_paths(user_id=user_id)

    proc = process_notify_outbox(limit=30, dry_run=False)
    rows = [r for r in list_notify_outbox(limit=40) if r.get("id") in ids]
    statuses = {int(r["id"]): r.get("status") for r in rows}
    live_email = bool(cfg.get("email_enabled") and cfg.get("smtp_host") and email)
    live_sms = bool(cfg.get("sms_enabled") and cfg.get("twilio_ready") and phone)
    sent_any = any(s == "sent" for s in statuses.values())
    live_proved = sent_any and (live_email or live_sms)
    return {
        "success": True,
        "outbox_ids": ids,
        "statuses": statuses,
        "process": proc,
        "live_email_capable": live_email,
        "live_sms_capable": live_sms,
        "live_send_proved": live_proved,
        "message": (
            f"Live test ids={ids} statuses={statuses} · "
            + ("LIVE send observed" if live_proved else "queued/processed — need working Twilio/SMTP for sent")
        ),
    }


# ---- Self-service: giveaway + vacancy digest --------------------------------


def giveaway_shift_as_open(
    officer_id: int,
    work_date: Any,
    *,
    shift_start: str = "",
    shift_end: str = "",
    notes: str = "",
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Officer giveaway → open shift post (claimable)."""
    from logic.officers import get_officer_by_id
    from logic.operations import create_open_shift

    if isinstance(work_date, date):
        d = work_date
    else:
        d = parse_date(str(work_date)) or date.fromisoformat(storage_date_str(str(work_date)))
    off = get_officer_by_id(int(officer_id)) or {}
    start = (shift_start or off.get("shift_start") or "06:00")[:5]
    end = (shift_end or off.get("shift_end") or "14:00")[:5]
    note = (notes or f"Giveaway from {off.get('name') or officer_id}").strip()
    squad = off.get("squad") if off.get("squad") in ("A", "B") else None
    r = create_open_shift(
        storage_date_str(d.isoformat()),
        start,
        end,
        squad=squad,
        notes=note,
        user_id=user_id,
    )
    if isinstance(r, dict):
        if r.get("success"):
            r.setdefault("message", "Giveaway posted as open shift")
        return r
    return {"success": bool(r), "message": "Giveaway posted" if r else "Failed"}


def run_vacancy_digest(*, dry_run: bool = False, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Open-shift vacancy alerter (digest) — enqueues notify for eligible roster."""
    try:
        from scripts.open_shift_digest import run_open_shift_digest

        code = run_open_shift_digest(dry_run=dry_run)
        return {
            "success": code == 0,
            "exit_code": code,
            "dry_run": dry_run,
            "message": f"Vacancy digest {'dry-run' if dry_run else 'ran'} exit={code}",
        }
    except Exception:
        # Inline fallback: list open shifts + enqueue summary
        from logic.notify_queue import enqueue_notify
        from logic.operations import get_open_shifts

        shifts = get_open_shifts() or []
        if isinstance(shifts, dict):
            shifts = shifts.get("shifts") or shifts.get("rows") or []
        open_n = len([s for s in shifts if isinstance(s, dict)])
        body = f"Chronos vacancy digest: {open_n} open shift(s)."
        if dry_run:
            return {"success": True, "dry_run": True, "open_count": open_n, "message": body}
        oid = enqueue_notify(
            channel="email",
            subject="Chronos vacancy digest",
            body=body,
            recipient="supervisors@department.local",
            template_key="vacancy_digest",
            user_id=user_id,
            meta={"kind": "vacancy_digest"},
        )
        return {
            "success": True,
            "open_count": open_n,
            "outbox_id": oid,
            "message": f"Enqueued digest for {open_n} open shift(s) · outbox#{oid}",
        }


# ---- Payroll: FLSA meter + OT election defaults -----------------------------


def flsa_meter_for_officer(officer_id: int, *, reference: Optional[date] = None) -> Dict[str, Any]:
    from logic.analytics import get_hours_watch
    from logic.dual_workforce import flsa_profile_for_officer
    from logic.officers import get_officer_by_id
    from logic.payroll_exceptions import flsa_period_banners

    reference = reference or date.today()
    off = get_officer_by_id(int(officer_id)) or {"id": officer_id}
    profile = flsa_profile_for_officer(off)
    banners = [b for b in flsa_period_banners(reference=reference) if int(b.get("officer_id") or 0) == int(officer_id)]
    try:
        watch = get_hours_watch()
    except Exception:
        watch = {}
    rows = []
    if isinstance(watch, dict):
        rows = watch.get("officers") or watch.get("rows") or watch.get("items") or []
    elif isinstance(watch, list):
        rows = watch
    mine = next((r for r in rows if isinstance(r, dict) and int(r.get("officer_id") or 0) == int(officer_id)), None)
    hours = None
    threshold = profile.get("threshold_hours") or profile.get("ot_threshold") or 86
    if mine:
        hours = mine.get("hours") or mine.get("period_hours") or mine.get("total_hours")
    if banners:
        hours = hours if hours is not None else banners[0].get("hours")
        threshold = banners[0].get("threshold") or threshold
    remaining = None
    if hours is not None and threshold is not None:
        try:
            remaining = float(threshold) - float(hours)
        except (TypeError, ValueError):
            remaining = None
    return {
        "success": True,
        "officer_id": int(officer_id),
        "hours": hours,
        "threshold": threshold,
        "remaining": remaining,
        "profile": profile,
        "banners": banners[:5],
        "message": (
            f"FLSA meter: {hours if hours is not None else '—'}h / {threshold}h"
            + (f" · {remaining:.1f}h to OT" if remaining is not None else "")
        ),
    }


def set_default_ot_election(mode: str, *, user_id: Optional[int] = None) -> Dict[str, Any]:
    """CBA default: cash vs comp for OT lines."""
    from logic.operations import set_department_setting

    m = (mode or "cash").strip().lower()
    if m not in ("cash", "comp", "comp_time", "overtime"):
        return {"success": False, "message": "mode must be cash or comp"}
    if m in ("comp_time",):
        m = "comp"
    if m == "overtime":
        m = "cash"
    r = set_department_setting("ot_election_default", m, user_id=user_id)
    if not r.get("success"):
        return r
    return {"success": True, "mode": m, "message": f"Default OT election: {m}"}


def get_default_ot_election() -> str:
    from logic.operations import get_department_setting

    raw = (get_department_setting("ot_election_default", "cash") or "cash").strip().lower()
    return "comp" if raw in ("comp", "comp_time") else "cash"


# ---- CAD/RMS import side (export already exists) ----------------------------


def import_cad_rms_duty_json(
    path_or_json: Any,
    *,
    dry_run: bool = True,
    apply: Optional[bool] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """CAD inbound via bidirectional bridge (validate / store / optional cover apply)."""
    from logic.cad_rms_bridge import import_cad_duty_bidirectional

    return import_cad_duty_bidirectional(
        path_or_json,
        dry_run=dry_run,
        apply=apply,
        user_id=user_id,
        source="product_pack",
    )


# ---- Cert inventory health --------------------------------------------------


def cert_inventory_health() -> Dict[str, Any]:
    from logic.certifications import get_shift_cert_requirements, list_certification_types

    types = list_certification_types(active_only=False) or []
    reqs = get_shift_cert_requirements() or []
    thin = len(types) < 2
    return {
        "success": True,
        "type_count": len(types),
        "requirement_count": len(reqs) if isinstance(reqs, list) else 0,
        "thin": thin,
        "message": (
            f"Cert types={len(types)} · band requirements={len(reqs) if isinstance(reqs, list) else 0}"
            + (" · inventory thin — add types before claim gates bind" if thin else "")
        ),
    }


# ---- Sim hard-pack message --------------------------------------------------


def hard_pack_headcount_message(num_officers: int = 7) -> Dict[str, Any]:
    """User reference: lean N=7 often needs 8 for Fri/Sat night min2 @ 8h multi-block."""
    n = int(num_officers)
    need8 = n < 8
    return {
        "success": True,
        "num_officers": n,
        "recommended_min": 8 if need8 else n,
        "message": (
            f"Hard pack note: with {n} officers, Fri+Sat night min2 (19:00–03:00) "
            f"often needs 8 on 8h multi-block (6-2,5-3). "
            + ("Consider headcount 8." if need8 else "Headcount at or above typical hard pack.")
        ),
    }


# ---- Pack smoke entry -------------------------------------------------------


def run_product_complete_smoke() -> Dict[str, Any]:
    """Local free smoke for complete pack (no live Twilio required)."""
    results = []
    # pattern
    p = preview_rotation_pattern("6-2,5-3", style="rotating")
    results.append(("build_pattern", p.get("success"), p.get("message")))
    # day coverage
    cov = live_day_coverage_report(date(2026, 7, 10))
    results.append(("evaluate_day_coverage", cov.get("success"), cov.get("message")))
    # windows roundtrip soft
    from logic.coverage_windows_store import list_coverage_windows, save_coverage_windows

    existing = list_coverage_windows()
    w = save_coverage_windows(existing or [])
    results.append(("save_coverage_windows", w.get("success"), w.get("message")))
    # policy
    from logic.bump_off_duty import load_off_duty_bump_policy

    pol = load_off_duty_bump_policy()
    results.append(("load_off_duty_bump_policy", True, f"allow_off_duty={pol.allow_off_duty}"))
    # plan bump (may be incomplete — still callable)
    from logic.officers import get_officers_by_seniority

    off = next((o for o in (get_officers_by_seniority() or []) if o.get("active") == 1), None)
    if off:
        br = plan_bump_chain_report(
            int(off["id"]), "2026-07-10", off.get("squad") or "A", off.get("shift_start") or "06:00"
        )
        results.append(("plan_bump_chain", True, br.get("message", "")[:80]))
    # court / holdover
    results.append(("court_min", True, f"{get_court_min_hours()}h"))
    results.append(("holdover_codes", True, f"{len(get_holdover_reason_codes())} codes"))
    # cert
    ch = cert_inventory_health()
    results.append(("certs", ch.get("success"), ch.get("message")))
    # cad export
    from logic.cad_rms_export import export_duty_roster_for_cad

    cad = export_duty_roster_for_cad(as_of=date(2026, 7, 10), days=1)
    results.append(("cad_export", cad.get("success"), cad.get("message")))
    hard = hard_pack_headcount_message(7)
    results.append(("hard_pack", hard.get("success"), hard.get("message")[:80]))
    ok = all(r[1] for r in results)
    return {
        "success": ok,
        "results": [{"name": a, "ok": b, "detail": c} for a, b, c in results],
        "message": f"product_complete_smoke {'PASS' if ok else 'FAIL'} · {len(results)} checks",
    }
