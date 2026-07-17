"""Constraint suggestions for Chronos simulator form.

Given already-locked constraints, propose logical values for the field the
user is about to fill. Suggestions are optional — never force a value.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def _f(val: Any) -> Optional[float]:
    try:
        if val is None or val == "":
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _i(val: Any) -> Optional[int]:
    try:
        if val is None or val == "":
            return None
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _parse_starts(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(s).strip() for s in raw if str(s).strip()]
    return [s.strip() for s in str(raw).replace(";", ",").split(",") if s.strip()]


def _parse_variations(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(t).strip() for t in raw if str(t).strip()]
    return [p.strip() for p in str(raw).replace(";", "|").split("|") if p.strip()]


def _pattern_duty_fraction(variations: Sequence[str]) -> Optional[float]:
    """Mean on/(on+off) across multi-block texts; None if unparseable."""
    from logic.rotation_patterns import parse_on_off_blocks

    fracs = []
    for text in variations:
        try:
            blocks = parse_on_off_blocks(text)
        except ValueError:
            continue
        if not blocks:
            continue
        on = sum(b.days_on for b in blocks)
        total = sum(b.length for b in blocks)
        if total > 0:
            fracs.append(on / total)
    if not fracs:
        return None
    return sum(fracs) / len(fracs)


def _annual_from_pattern(length: float, variations: Sequence[str]) -> Optional[float]:
    frac = _pattern_duty_fraction(variations)
    if frac is None or length <= 0:
        return None
    # Year-average using 365.25 (matches product annual math band)
    return round(frac * 365.25 * float(length), 1)


def _locked_summary(ctx: Dict[str, Any]) -> str:
    bits = []
    if ctx.get("use_rotation") and ctx.get("rotation"):
        bits.append(f"rotation={ctx.get('rotation')}")
    if ctx.get("use_style") and ctx.get("variations"):
        bits.append(f"patterns={ctx.get('variations')}")
    if ctx.get("use_length") and ctx.get("length") not in (None, ""):
        bits.append(f"length={ctx.get('length')}h")
    if ctx.get("use_annual") and ctx.get("annual") not in (None, ""):
        bits.append(f"annual={ctx.get('annual')}±{ctx.get('annual_var') or '?'}")
    if ctx.get("use_officers") and ctx.get("officers") not in (None, ""):
        bits.append(f"N={ctx.get('officers')}")
    if ctx.get("use_starts") and ctx.get("starts"):
        bits.append(f"starts={ctx.get('starts')}")
    if ctx.get("use_247") and ctx.get("cov247") not in (None, ""):
        bits.append(f"24/7≥{ctx.get('cov247')}")
    if ctx.get("use_windows") and ctx.get("windows"):
        bits.append(f"windows={len(ctx.get('windows') or [])}")
    if ctx.get("use_nearby") and ctx.get("nearby_hops") not in (None, ""):
        bits.append(f"bumps={ctx.get('nearby_hops')}")
    if ctx.get("allow_offday"):
        bits.append("off-day OT on")
    return "; ".join(bits) if bits else "(no other constraints locked yet)"


def _opt(label: str, values: Dict[str, Any], why: str, *, recommended: bool = False) -> Dict[str, Any]:
    return {
        "label": label,
        "values": values,
        "why": why,
        "recommended": recommended,
    }


def suggest_constraint(field: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return explanation + optional pick-list for *field* given locked *context*.

    ``values`` keys match form payload fields (length, annual, officers, starts, …).
    """
    ctx = dict(context or {})
    field = (field or "").strip().lower()
    summary = _locked_summary(ctx)
    options: List[Dict[str, Any]] = []
    title = "Suggested Values"
    explanation = f"Based on locked constraints: {summary}"

    length = _f(ctx.get("length")) if ctx.get("use_length") else None
    annual = _f(ctx.get("annual")) if ctx.get("use_annual") else None
    officers = _i(ctx.get("officers")) if ctx.get("use_officers") else None
    starts = _parse_starts(ctx.get("starts")) if ctx.get("use_starts") else []
    variations = _parse_variations(ctx.get("variations")) if ctx.get("use_style") else []
    rotation = (ctx.get("rotation") or "") if ctx.get("use_rotation") else ""
    cov247 = _i(ctx.get("cov247")) if ctx.get("use_247") else None
    windows = list(ctx.get("windows") or []) if ctx.get("use_windows") else []
    win_min = 0
    for w in windows:
        if not isinstance(w, dict) or w.get("enabled") is False:
            continue
        try:
            win_min = max(win_min, int(w.get("min_officers") or 0))
        except (TypeError, ValueError):
            pass
    rot_l = rotation.lower()
    wants_12h = any(k in rot_l for k in ("panama", "pitman", "dupont", "12"))
    multi_blockish = bool(variations) or "6-2" in str(ctx.get("variations") or "")

    if field in ("length", "shift_length", "shift_length_hours"):
        title = "Shift Length Suggestions"
        if variations and annual:
            # invert annual ≈ frac * 365.25 * L
            frac = _pattern_duty_fraction(variations)
            if frac and frac > 0:
                implied = round(float(annual) / (frac * 365.25) * 2) / 2
                if 6.0 <= implied <= 14.0:
                    options.append(
                        _opt(
                            f"{implied:g}h (matches annual + pattern)",
                            {"length": str(implied), "use_length": True},
                            f"Duty fraction ≈ {frac:.2%} → L ≈ {implied:g}h for {annual:g} annual hours.",
                            recommended=True,
                        )
                    )
        if variations and not annual:
            for L in (8.0, 10.0, 12.0):
                ann = _annual_from_pattern(L, variations)
                if ann:
                    options.append(
                        _opt(
                            f"{L:g}h → ~{ann:g} annual",
                            {
                                "length": str(L),
                                "use_length": True,
                                "annual": str(int(round(ann))),
                                "annual_var": "20",
                                "use_annual": True,
                            },
                            f"Pattern duty × {L:g}h projects ~{ann:g} h/year.",
                            recommended=(L == 8.0 and multi_blockish),
                        )
                    )
        if wants_12h:
            options.insert(
                0,
                _opt(
                    "12h (Pitman / Panama / DuPont class)",
                    {"length": "12", "use_length": True},
                    "Selected rotation is commonly paired with 12-hour shifts.",
                    recommended=True,
                ),
            )
        if not options:
            options = [
                _opt(
                    "8h three/four-band patrol",
                    {"length": "8", "use_length": True},
                    "Common LE 24/7 pack.",
                    recommended=True,
                ),
                _opt("10h compressed", {"length": "10", "use_length": True}, "Fewer handoffs; longer days."),
                _opt("12h Panama/Pitman", {"length": "12", "use_length": True}, "Two-platoon twelve-hour."),
            ]

    elif field in ("annual", "annual_hours", "annual_var", "annual_hours_target"):
        title = "Annual Hours Suggestions"
        if length and variations:
            ann = _annual_from_pattern(length, variations)
            if ann:
                options.append(
                    _opt(
                        f"{int(round(ann))} ± 20 (from pattern × length)",
                        {
                            "annual": str(int(round(ann))),
                            "annual_var": "20",
                            "use_annual": True,
                        },
                        f"{length:g}h × pattern duty projects ~{ann:g} h/year. ±20 is a tight LE band.",
                        recommended=True,
                    )
                )
                options.append(
                    _opt(
                        f"{int(round(ann))} ± 40 (looser band)",
                        {
                            "annual": str(int(round(ann))),
                            "annual_var": "40",
                            "use_annual": True,
                        },
                        "Same mean with wider fairness band for phase stagger.",
                    )
                )
        if length and not variations:
            # 5-2 style ≈ 5/7
            for frac, lab in ((5 / 7, "5-2 style"), (11 / 16, "6-2,5-3 multi-block"), (0.5, "half duty")):
                ann = round(frac * 365.25 * length, 1)
                options.append(
                    _opt(
                        f"{int(round(ann))} ± 20 ({lab})",
                        {"annual": str(int(round(ann))), "annual_var": "20", "use_annual": True},
                        f"Assumes ~{frac:.0%} duty at {length:g}h.",
                        recommended=(lab.startswith("6-2") and abs(length - 8) < 0.1),
                    )
                )
        if not options:
            options = [
                _opt(
                    "2008 ± 20 (8h multi-block ref)",
                    {"annual": "2008", "annual_var": "20", "use_annual": True},
                    "11/16 duty × 8h ≈ 2008.",
                    recommended=True,
                ),
                _opt(
                    "2080 ± 40 (full-time 40h week)",
                    {"annual": "2080", "annual_var": "40", "use_annual": True},
                    "Common FTE year.",
                ),
            ]

    elif field in ("officers", "num_officers", "officer_count"):
        title = "Officer Count Suggestions"
        body_floor = max(int(cov247 or 0), int(win_min or 0), 1)
        if cov247 or win_min:
            # 8h three-band Fri/Sat min-2 night often needs 7–8 with multi-block
            if (length or 8) <= 9 and win_min >= 2 and (cov247 or 0) >= 1:
                options.append(
                    _opt(
                        "8 officers (hard Fri/Sat nights + 24/7)",
                        {"officers": "8", "use_officers": True},
                        "8h multi-block with 24/7 min-1 and Fri/Sat 19–03 min-2 usually needs 8 on-duty capacity.",
                        recommended=True,
                    )
                )
                options.append(
                    _opt(
                        "7 officers (may leave thin nights)",
                        {"officers": "7", "use_officers": True},
                        "Can hard-OK with good stagger + evening pack; residual risk on nights without off-day OT.",
                    )
                )
                options.append(
                    _opt(
                        "9 officers (cushion)",
                        {"officers": "9", "use_officers": True},
                        "Extra body for leave / windows.",
                    )
                )
            else:
                n0 = max(body_floor * 3, body_floor + 2, 4)
                options.append(
                    _opt(
                        f"{n0} officers (coverage floor × bands)",
                        {"officers": str(n0), "use_officers": True},
                        f"From 24/7≥{cov247 or 0} and window min≥{win_min}.",
                        recommended=True,
                    )
                )
        if starts:
            n_band = len(starts)
            options.append(
                _opt(
                    f"{n_band * 2} officers (2 per start band)",
                    {"officers": str(n_band * 2), "use_officers": True},
                    f"{n_band} start band(s) × 2 for relief.",
                    recommended=not options,
                )
            )
        if not options:
            options = [
                _opt("8 officers", {"officers": "8", "use_officers": True}, "Small-dept 24/7 ref.", recommended=True),
                _opt("12 officers", {"officers": "12", "use_officers": True}, "Larger relief pool."),
            ]

    elif field in ("starts", "shift_starts"):
        title = "Shift Start Pack Suggestions"
        L = length or 8.0
        if L <= 9:
            options.append(
                _opt(
                    "06:00, 14:00, 19:00, 22:00 (evening pack)",
                    {"starts": "06:00, 14:00, 19:00, 22:00", "use_starts": True},
                    "8h LE pack with dedicated 19:00 for Fri/Sat night windows.",
                    recommended=bool(win_min >= 2) or not starts,
                )
            )
            options.append(
                _opt(
                    "06:00, 14:00, 22:00 (classic 3-band)",
                    {"starts": "06:00, 14:00, 22:00", "use_starts": True},
                    "Equal 8h spine; nights via 14:00+22:00 overlap.",
                )
            )
            options.append(
                _opt(
                    "07:00, 15:00, 19:00, 23:00",
                    {"starts": "07:00, 15:00, 19:00, 23:00", "use_starts": True},
                    "Hour-shifted evening pack.",
                )
            )
        elif L <= 11:
            options.append(
                _opt(
                    "06:00, 14:00, 22:00",
                    {"starts": "06:00, 14:00, 22:00", "use_starts": True},
                    f"{L:g}h three-band cover.",
                    recommended=True,
                )
            )
        else:
            options.append(
                _opt(
                    "06:00, 18:00 (12h dual)",
                    {"starts": "06:00, 18:00", "use_starts": True},
                    "Twelve-hour day/night platoon starts.",
                    recommended=True,
                )
            )
            options.append(
                _opt(
                    "07:00, 19:00",
                    {"starts": "07:00, 19:00", "use_starts": True},
                    "Alternate 12h anchors.",
                )
            )

    elif field in ("style", "variations", "multi_block", "rotation_style"):
        title = "Multi-Block Pattern Suggestions"
        if length and abs(length - 8) < 0.1:
            options.append(
                _opt(
                    "6-2,5-3 | 6-3,5-2 @ ~2008h",
                    {
                        "variations": "6-2,5-3 | 6-3,5-2",
                        "rot_style": "Rotating",
                        "use_style": True,
                        "annual": "2008",
                        "annual_var": "20",
                        "use_annual": True,
                    },
                    "11/16 duty × 8h ≈ 2008 annual — department multi-block ref.",
                    recommended=True,
                )
            )
        if length and abs(length - 12) < 0.1:
            options.append(
                _opt(
                    "2-2,3-2,2-3 (Pitman blocks)",
                    {
                        "variations": "2-2,3-2,2-3",
                        "rot_style": "Rotating",
                        "use_style": True,
                    },
                    "Common 12h Pitman on/off blocks.",
                    recommended=True,
                )
            )
        options.append(
            _opt(
                "5-2 fixed (weekdays)",
                {"variations": "5-2", "rot_style": "Fixed", "use_style": True},
                "Mon–Fri style fixed block.",
            )
        )
        options.append(
            _opt(
                "5-2,6-3 | 5-3,6-2",
                {
                    "variations": "5-2,6-3 | 5-3,6-2",
                    "rot_style": "Rotating",
                    "use_style": True,
                },
                "Alternate multi-block pair (same cycle family).",
            )
        )

    elif field in ("rotation", "rotation_type"):
        title = "Rotation Preset Suggestions"
        if length and length >= 11.5:
            options.append(
                _opt(
                    "Pitman 2-2-3 (12h)",
                    {"rotation": "Pitman 2-2-3 (12h)", "use_rotation": True},
                    "Matches 12h length class.",
                    recommended=True,
                )
            )
            options.append(
                _opt(
                    "Panama 12-hour",
                    {"rotation": "Panama 12-hour", "use_rotation": True},
                    "Half-cycle A then B.",
                )
            )
        if multi_blockish or (length and abs(length - 8) < 0.1):
            options.append(
                _opt(
                    "2-2-3 (14-day) + multi-block patterns",
                    {
                        "rotation": "2-2-3 (14-day)",
                        "use_rotation": True,
                        "variations": "6-2,5-3 | 6-3,5-2",
                        "rot_style": "Rotating",
                        "use_style": True,
                    },
                    "Host preset for multi-block 8h work.",
                    recommended=True,
                )
            )
        if not options:
            options = [
                _opt(
                    "2-2-3 (14-day)",
                    {"rotation": "2-2-3 (14-day)", "use_rotation": True},
                    "Default squad skeleton.",
                    recommended=True,
                ),
                _opt("4-on-4-off", {"rotation": "4-on-4-off", "use_rotation": True}, "Equal A/B eight-day."),
                _opt(
                    "5-2 fixed (M-F style)",
                    {"rotation": "5-2 fixed (M-F style)", "use_rotation": True},
                    "Weekday fixed.",
                ),
            ]

    elif field in ("coverage_247", "cov247", "247"):
        title = "24/7 Minimum Suggestions"
        options = [
            _opt(
                "Min 1 on duty always",
                {"cov247": "1", "use_247": True},
                "Standard continuous coverage floor.",
                recommended=True,
            ),
            _opt("Min 2 on duty always", {"cov247": "2", "use_247": True}, "Stronger floor; needs more headcount."),
        ]
        if officers and officers < 6:
            options.insert(
                0,
                _opt(
                    "Min 1 (fits small roster)",
                    {"cov247": "1", "use_247": True},
                    f"With N={officers}, min-2 24/7 is often infeasible.",
                    recommended=True,
                ),
            )

    elif field in ("windows", "extra_windows", "use_windows"):
        title = "Staffing Window Suggestions"
        options.append(
            _opt(
                "Fri+Sat 19:00–03:00 min 2",
                {
                    "use_windows": True,
                    "windows": [
                        {
                            "min_officers": 2,
                            "start_time": "19:00",
                            "end_time": "03:00",
                            "weekday": 4,
                            "label": "Friday Night",
                            "enabled": True,
                        },
                        {
                            "min_officers": 2,
                            "start_time": "19:00",
                            "end_time": "03:00",
                            "weekday": 5,
                            "label": "Saturday Night",
                            "enabled": True,
                        },
                    ],
                },
                "High-risk weekend nights — common LE hard window pair."
                + (" Pair with 8 officers + evening starts." if (officers or 0) < 8 else ""),
                recommended=True,
            )
        )
        options.append(
            _opt(
                "No extra windows",
                {"use_windows": False, "windows": []},
                "Only 24/7 / min-per-shift floors.",
            )
        )

    elif field in ("nearby", "nearby_hops", "bumps"):
        title = "Nearby Start Bump Suggestions"
        options = [
            _opt(
                "1 bump (home ±1 pack band)",
                {"nearby_hops": "1", "use_nearby": True},
                "e.g. home 19:00 → 14:00 or 22:00 on ON days only.",
                recommended=True,
            ),
            _opt(
                "2 bumps (wider flex)",
                {"nearby_hops": "2", "use_nearby": True},
                "More start mobility; still ON-day only unless off-day OT is on.",
            ),
            _opt(
                "0 bumps (prefer home only)",
                {"nearby_hops": "0", "use_nearby": True},
                "Stay on home start when seats allow.",
            ),
        ]

    elif field in ("min_ps", "min_per_shift"):
        title = "Min Per Shift Suggestions"
        options = [
            _opt(
                "1 per start band",
                {"min_ps": "1", "use_min_ps": True},
                "Usual floor with flexible daily rebalance.",
                recommended=True,
            ),
            _opt("2 per start band", {"min_ps": "2", "use_min_ps": True}, "Heavier desk model — needs more officers."),
        ]

    elif field in ("flsa", "flsa_days"):
        title = "FLSA Suggestions"
        options = [
            _opt(
                "28-day / §207(k) LE period",
                {"flsa_days": "28", "use_flsa": True},
                "Default law-enforcement work period election.",
                recommended=True,
            ),
            _opt(
                "7-day period",
                {"flsa_days": "7", "use_flsa": True},
                "Weekly FLSA window.",
            ),
        ]

    elif field in ("offday", "allow_offday"):
        title = "Off-Day Coverage"
        options = [
            _opt(
                "Keep off-day OT OFF (rotation only)",
                {"allow_offday": False},
                "Only ON days work — respects multi-block OFF.",
                recommended=True,
            ),
            _opt(
                "Allow off-day OT call-in",
                {"allow_offday": True},
                "OFF officers may fill windows when ON bodies are short (optional).",
            ),
        ]

    else:
        title = "Constraint Help"
        explanation = f"No specialized suggestions for '{field}'. Locked so far: {summary}. Enter any value you need."

    # De-dupe labels
    seen = set()
    uniq = []
    for o in options:
        lab = o.get("label")
        if lab in seen:
            continue
        seen.add(lab)
        uniq.append(o)

    # Sort recommended first
    uniq.sort(key=lambda o: 0 if o.get("recommended") else 1)

    return {
        "success": True,
        "field": field,
        "title": title,
        "explanation": explanation,
        "context_summary": summary,
        "options": uniq,
        "allow_custom": True,
        "custom_hint": "Or type any other value in the form — suggestions never lock you in.",
    }


def context_has_locked_constraints(context: Optional[Dict[str, Any]]) -> bool:
    ctx = context or {}
    flags = (
        "use_rotation",
        "use_officers",
        "use_length",
        "use_annual",
        "use_starts",
        "use_min_ps",
        "use_247",
        "use_style",
        "use_windows",
        "use_nearby",
        "use_flsa",
        "allow_offday",
    )
    return any(bool(ctx.get(k)) for k in flags)
