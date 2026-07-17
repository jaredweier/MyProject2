"""Dual workforce FLSA engine — sworn §7(k) + civilian weekly 40h (Netchex pattern).

Settings keys (canonical, shared with labor_compliance):
  flsa_dual_workforce / dual_flsa_enabled (both accepted)
  flsa_civilian_weekly_threshold
  flsa_comp_cap_sworn / flsa_comp_cap_civilian
  flsa_work_period_days
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple


def _truthy(raw: str) -> bool:
    return (raw or "").strip().lower() in ("1", "true", "yes", "on")


def get_dual_workforce_settings() -> Dict[str, Any]:
    from logic.operations import get_department_setting

    def g(key: str, default: str = "") -> str:
        return (get_department_setting(key, default) or default).strip()

    # Accept both key families so Deploy UI and Payroll UI stay in sync
    dual = _truthy(g("flsa_dual_workforce", "")) or _truthy(g("dual_flsa_enabled", "0"))
    try:
        civ_thr = float(g("flsa_civilian_weekly_threshold", "40") or 40)
    except (TypeError, ValueError):
        civ_thr = 40.0
    try:
        sworn_cap = float(g("flsa_comp_cap_sworn", g("comp_cap_sworn", "480")) or 480)
    except (TypeError, ValueError):
        sworn_cap = 480.0
    try:
        civ_cap = float(g("flsa_comp_cap_civilian", g("comp_cap_civilian", "240")) or 240)
    except (TypeError, ValueError):
        civ_cap = 240.0
    try:
        period_days = int(float(g("flsa_work_period_days", "14") or 14))
    except (TypeError, ValueError):
        period_days = 14
    period_days = max(7, min(period_days, 28))
    return {
        "dual_flsa_enabled": dual,
        "dual_workforce": dual,
        "civilian_weekly_threshold": civ_thr,
        "comp_cap_sworn": sworn_cap,
        "comp_cap_civilian": civ_cap,
        "sworn_comp_cap": sworn_cap,
        "civilian_comp_cap": civ_cap,
        "sworn_default_period_days": period_days,
        "work_period_days": period_days,
    }


def save_dual_workforce_settings(
    *,
    dual_flsa_enabled: bool,
    civilian_weekly_threshold: float = 40.0,
    comp_cap_sworn: float = 480.0,
    comp_cap_civilian: float = 240.0,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    from logic.operations import set_department_setting

    on = "1" if dual_flsa_enabled else "0"
    # Write both key families
    set_department_setting("dual_flsa_enabled", on)
    set_department_setting("flsa_dual_workforce", on)
    set_department_setting("flsa_civilian_weekly_threshold", str(civilian_weekly_threshold))
    set_department_setting("comp_cap_sworn", str(comp_cap_sworn))
    set_department_setting("comp_cap_civilian", str(comp_cap_civilian))
    set_department_setting("flsa_comp_cap_sworn", str(comp_cap_sworn))
    set_department_setting("flsa_comp_cap_civilian", str(comp_cap_civilian))
    try:
        from logic.users import log_audit_action

        log_audit_action(
            "payroll.dual_workforce_saved",
            "department_settings",
            None,
            user_id,
            f"dual={dual_flsa_enabled} civ_thr={civilian_weekly_threshold}",
        )
    except Exception:
        pass
    return {"success": True, "settings": get_dual_workforce_settings()}


def flsa_profile_for_officer(officer: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return OT basis, thresholds, and comp cap for one officer."""
    settings = get_dual_workforce_settings()
    wc = str((officer or {}).get("workforce_class") or "sworn").lower()
    if wc not in ("sworn", "civilian"):
        wc = "sworn"
    if settings["dual_flsa_enabled"] and wc == "civilian":
        return {
            "workforce_class": "civilian",
            "ot_basis": "weekly_40",
            "weekly_threshold": float(settings["civilian_weekly_threshold"]),
            "work_period_days": 7,
            "period_threshold": float(settings["civilian_weekly_threshold"]),
            "comp_cap": float(settings["comp_cap_civilian"]),
            "uses_7k": False,
        }
    # Sworn (or dual off — everyone on 7k-style department period)
    try:
        from logic.labor_compliance import flsa_threshold_for_period_days

        thr = flsa_threshold_for_period_days(int(settings["sworn_default_period_days"]))
    except Exception:
        thr = 86.0 if int(settings["sworn_default_period_days"]) == 14 else 171.0
    return {
        "workforce_class": "sworn" if not settings["dual_flsa_enabled"] else wc,
        "ot_basis": "7k_work_period",
        "weekly_threshold": None,
        "work_period_days": int(settings["sworn_default_period_days"]),
        "period_threshold": float(thr),
        "comp_cap": float(settings["comp_cap_sworn"]),
        "uses_7k": True,
    }


def comp_cap_for_officer(officer: Optional[Dict[str, Any]]) -> float:
    return float(flsa_profile_for_officer(officer).get("comp_cap") or 480.0)


def _week_bounds(d: date) -> Tuple[date, date]:
    """Monday–Sunday containing d (ISO week)."""
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def _sum_hours(officer_id: int, start: date, end: date) -> float:
    from logic.labor_compliance import sum_officer_work_hours

    return float(sum_officer_work_hours(int(officer_id), start, end))


def compute_officer_ot_split(
    officer_id: int,
    *,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    reference: Optional[date] = None,
) -> Dict[str, Any]:
    """Split regular vs OT hours for one officer under dual or single FLSA profile.

    Civilian (dual on): weekly threshold (default 40h) per ISO week overlapping range.
    Sworn: §7(k) work-period threshold for period containing *reference*.
    """
    from logic.officers import get_officer_by_id
    from logic.payroll import get_pay_period

    officer = get_officer_by_id(int(officer_id))
    if not officer:
        return {"success": False, "message": "Officer not found"}

    profile = flsa_profile_for_officer(officer)
    ref = reference or date.today()
    if period_start is None or period_end is None:
        ps, pe = get_pay_period(ref)
        period_start = period_start or ps
        period_end = period_end or pe

    total = _sum_hours(int(officer_id), period_start, period_end)
    regular = 0.0
    overtime = 0.0
    week_rows: List[Dict[str, Any]] = []

    if profile.get("ot_basis") == "weekly_40":
        thr = float(profile["weekly_threshold"] or 40)
        # Walk each ISO week overlapping the pay window
        cur = period_start
        seen = set()
        while cur <= period_end:
            ws, we = _week_bounds(cur)
            key = ws.isoformat()
            if key not in seen:
                seen.add(key)
                # Hours in intersection of week and pay period
                a = max(ws, period_start)
                b = min(we, period_end)
                wh = _sum_hours(int(officer_id), a, b)
                reg = min(wh, thr)
                ot = max(0.0, wh - thr)
                regular += reg
                overtime += ot
                week_rows.append(
                    {
                        "week_start": ws.isoformat(),
                        "week_end": we.isoformat(),
                        "hours": round(wh, 2),
                        "regular": round(reg, 2),
                        "overtime": round(ot, 2),
                        "threshold": thr,
                    }
                )
            cur += timedelta(days=1)
        basis_label = f"civilian weekly {thr:.0f}h"
    else:
        # Sworn §7(k): OT above period threshold (may use FLSA work period not pay period)
        try:
            from logic.labor_compliance import (
                flsa_threshold_for_period_days,
                get_flsa_work_period,
                get_flsa_work_period_days,
            )

            flsa_start, flsa_end = get_flsa_work_period(ref)
            thr = float(profile.get("period_threshold") or flsa_threshold_for_period_days(get_flsa_work_period_days()))
            # Hours in FLSA work period (true 7k basis)
            flsa_hours = _sum_hours(int(officer_id), flsa_start, flsa_end)
            # Also report pay-period hours for finance
            pay_hours = total
            ot_flsa = max(0.0, flsa_hours - thr)
            # Map OT share onto pay window proportionally if needed
            if pay_hours <= 0:
                regular, overtime = 0.0, 0.0
            elif flsa_hours <= 0:
                regular, overtime = pay_hours, 0.0
            else:
                # OT hours that fall in this pay window ≈ pay_hours * (ot_flsa / flsa_hours)
                overtime = min(pay_hours, pay_hours * (ot_flsa / flsa_hours) if flsa_hours else 0.0)
                regular = max(0.0, pay_hours - overtime)
            week_rows.append(
                {
                    "flsa_period_start": flsa_start.isoformat(),
                    "flsa_period_end": flsa_end.isoformat(),
                    "flsa_hours": round(flsa_hours, 2),
                    "pay_period_hours": round(pay_hours, 2),
                    "threshold": thr,
                    "regular": round(regular, 2),
                    "overtime": round(overtime, 2),
                }
            )
            basis_label = f"sworn §7(k) {profile.get('work_period_days')}d / {thr:.0f}h"
            total = pay_hours
        except Exception:
            thr = float(profile.get("period_threshold") or 86)
            regular = min(total, thr)
            overtime = max(0.0, total - thr)
            basis_label = f"sworn period {thr:.0f}h"

    force_cash = False
    try:
        from logic.banked_time import get_officer_time_banks

        banks = get_officer_time_banks(int(officer_id)) or {}
        comp = 0.0
        if isinstance(banks, dict):
            if "comp_hours" in banks:
                comp = float(banks.get("comp_hours") or 0)
            else:
                for row in banks.get("banks") or banks.get("rows") or []:
                    if isinstance(row, dict) and str(row.get("bank_type") or row.get("type") or "").lower() in (
                        "comp",
                        "comp_time",
                        "compensatory",
                    ):
                        comp = float(row.get("balance") or row.get("hours") or 0)
                        break
        cap = float(profile["comp_cap"])
        force_cash = comp >= cap - 0.01
    except Exception:
        cap = float(profile["comp_cap"])
        force_cash = False

    return {
        "success": True,
        "officer_id": int(officer_id),
        "officer_name": officer.get("name"),
        "workforce_class": profile["workforce_class"],
        "ot_basis": profile["ot_basis"],
        "basis_label": basis_label,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "total_hours": round(total, 2),
        "regular_hours": round(regular, 2),
        "overtime_hours": round(overtime, 2),
        "comp_cap": float(profile["comp_cap"]),
        "force_cash_ot": force_cash,
        "detail": week_rows,
        "uses_7k": bool(profile.get("uses_7k")),
    }


def run_dual_period_ot_ledger(
    *,
    period_start: Optional[date] = None,
    reference: Optional[date] = None,
) -> Dict[str, Any]:
    """Department OT ledger: sworn 7k + civilian weekly in one pass."""
    from logic.officers import get_officers_by_seniority
    from logic.payroll import get_pay_period
    from validators import is_officer_active

    ref = reference or date.today()
    ps, pe = get_pay_period(period_start or ref)
    settings = get_dual_workforce_settings()
    rows: List[Dict[str, Any]] = []
    for o in get_officers_by_seniority() or []:
        if not is_officer_active(o):
            continue
        split = compute_officer_ot_split(int(o["id"]), period_start=ps, period_end=pe, reference=ref)
        if split.get("success"):
            rows.append(split)
    sworn_ot = sum(r["overtime_hours"] for r in rows if r.get("workforce_class") == "sworn")
    civ_ot = sum(r["overtime_hours"] for r in rows if r.get("workforce_class") == "civilian")
    return {
        "success": True,
        "dual_enabled": settings["dual_flsa_enabled"],
        "period_start": ps.isoformat(),
        "period_end": pe.isoformat(),
        "rows": rows,
        "count": len(rows),
        "sworn_ot_hours": round(sworn_ot, 2),
        "civilian_ot_hours": round(civ_ot, 2),
        "total_ot_hours": round(sworn_ot + civ_ot, 2),
    }


def export_dual_ot_ledger_csv(
    *,
    period_start: Optional[date] = None,
) -> Dict[str, Any]:
    from datetime import datetime
    from pathlib import Path

    from paths import data_path

    ledger = run_dual_period_ot_ledger(period_start=period_start)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(data_path("exports")) / f"dual_ot_ledger_{stamp}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "officer_id,officer_name,workforce_class,ot_basis,total_hours,regular_hours,overtime_hours,comp_cap,force_cash_ot"
    ]
    for r in ledger.get("rows") or []:
        lines.append(
            f"{r.get('officer_id')},"
            f'"{(r.get("officer_name") or "").replace(chr(34), "")}",'
            f"{r.get('workforce_class')},"
            f"{r.get('ot_basis')},"
            f"{r.get('total_hours')},"
            f"{r.get('regular_hours')},"
            f"{r.get('overtime_hours')},"
            f"{r.get('comp_cap')},"
            f"{1 if r.get('force_cash_ot') else 0}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"success": True, "path": str(path), "count": ledger.get("count", 0), "ledger": ledger}
