use std::collections::{HashMap, HashSet};

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use crate::compliance::{
    consecutive_work_message, exceeds_consecutive_work_limit, CoveringShiftStarts,
};
use crate::coverage::compute_shift_coverage_counts;
use crate::rest::{meets_minimum_rest, minimum_rest_message, shift_end_for};
use crate::rotation::{is_high_risk_night_ordinal, parse_ymd, RotationSchedule};
use crate::status::{is_command_staff_title, Officer, OverrideMaps};

#[derive(Clone)]
pub struct OfficerFull {
    pub id: i64,
    pub name: String,
    pub squad: String,
    pub shift_start: String,
    pub shift_end: String,
    pub active: bool,
    pub job_title: String,
    pub seniority_rank: i32,
}

fn is_night_shift(shift_start: &str) -> bool {
    let hour: i32 = shift_start
        .split(':')
        .next()
        .and_then(|h| h.parse().ok())
        .unwrap_or(12);
    hour >= 18 || hour < 6
}

fn parse_minutes(value: &str) -> i32 {
    let parts: Vec<&str> = value.split(':').collect();
    if parts.len() < 2 {
        return 0;
    }
    let h: i32 = parts[0].parse().unwrap_or(0);
    let m: i32 = parts[1].parse().unwrap_or(0);
    h * 60 + m
}

fn schedule_working(status: &str) -> bool {
    matches!(status, "working" | "covering" | "swapped" | "training")
}

fn replacement_shift_for_rules(officer: &OfficerFull, day_context: Option<&(String, String)>) -> String {
    if let Some((status, assigned)) = day_context {
        if schedule_working(status) && !assigned.is_empty() {
            return assigned.clone();
        }
    }
    officer.shift_start.clone()
}

fn shift_bands(bump_rules: &HashMap<String, Vec<String>>) -> Vec<String> {
    let mut bands: Vec<String> = bump_rules.keys().cloned().collect();
    bands.sort_by_key(|s| parse_minutes(s));
    bands
}

fn normalize_shift_band(shift_start: &str, bands: &[String]) -> String {
    if shift_start.is_empty() {
        return String::new();
    }
    if bands.iter().any(|b| b == shift_start) {
        return shift_start.to_string();
    }
    let target = parse_minutes(shift_start);
    bands
        .iter()
        .min_by_key(|b| (parse_minutes(b) - target).abs())
        .cloned()
        .unwrap_or_else(|| shift_start.to_string())
}

fn can_cover_shift(
    replacement_start: &str,
    covered_start: &str,
    bump_rules: &HashMap<String, Vec<String>>,
    bands: &[String],
) -> bool {
    let replacement = normalize_shift_band(replacement_start, bands);
    let covered = normalize_shift_band(covered_start, bands);
    if replacement.is_empty() || covered.is_empty() {
        return false;
    }
    bump_rules
        .get(&covered)
        .map(|allowed| allowed.iter().any(|s| s == &replacement))
        .unwrap_or(false)
}

fn assignment_exhausted(officer_id: i64, counts: &HashMap<i64, i32>, max_assignments: i32) -> bool {
    counts.get(&officer_id).copied().unwrap_or(0) >= max_assignments
}

fn shift_retains_coverage_after_bump(
    vacating_id: i64,
    vacated_shift: &str,
    squad: &str,
    officers: &[OfficerFull],
    day_context: &HashMap<i64, (String, String)>,
    excluded: &HashSet<i64>,
    bands: &[String],
) -> bool {
    let vacated_band = normalize_shift_band(vacated_shift, bands);
    if vacated_band.is_empty() {
        return false;
    }
    for off in officers {
        if !off.active || off.squad != squad || is_command_staff_title(&off.job_title) {
            continue;
        }
        if off.id == vacating_id || excluded.contains(&off.id) {
            continue;
        }
        let Some((status, assigned)) = day_context.get(&off.id) else {
            continue;
        };
        if !schedule_working(status) {
            continue;
        }
        let home_raw = if assigned.is_empty() {
            off.shift_start.as_str()
        } else {
            assigned.as_str()
        };
        if normalize_shift_band(home_raw, bands) == vacated_band {
            return true;
        }
    }
    false
}

fn officer_full_to_status(off: &OfficerFull) -> Officer {
    Officer {
        id: off.id,
        squad: off.squad.clone(),
        shift_start: off.shift_start.clone(),
        active: off.active,
        job_title: off.job_title.clone(),
    }
}

struct ReplacementSearch {
    on_duty: Option<OfficerFull>,
    rest_blocked: Option<OfficerFull>,
    consecutive_blocked: Option<OfficerFull>,
}

fn find_replacement(
    squad: &str,
    shift_start: &str,
    officers: &[OfficerFull],
    assignment_counts: &HashMap<i64, i32>,
    max_assignments: i32,
    bump_rules: &HashMap<String, Vec<String>>,
    day_context: &HashMap<i64, (String, String)>,
    excluded: &HashSet<i64>,
    bands: &[String],
    request_ordinal: i32,
    base_ordinal: i32,
    schedule: &RotationSchedule,
    maps: &OverrideMaps,
    shift_times: &[(String, String)],
    covering_shifts: &CoveringShiftStarts,
    min_rest_hours: f64,
    max_consecutive_work_days: i32,
    enforce_minimum_rest: bool,
    enforce_consecutive_work: bool,
) -> ReplacementSearch {
    let covered_band = normalize_shift_band(shift_start, bands);
    let mut candidates: Vec<&OfficerFull> = officers
        .iter()
        .filter(|o| {
            o.active
                && o.squad == squad
                && !is_command_staff_title(&o.job_title)
                && !excluded.contains(&o.id)
                && !assignment_exhausted(o.id, assignment_counts, max_assignments)
                && can_cover_shift(
                    &replacement_shift_for_rules(o, day_context.get(&o.id)),
                    &covered_band,
                    bump_rules,
                    bands,
                )
        })
        .collect();
    // Junior bumps first — higher seniority_rank = more junior (matches Python).
    candidates.sort_by(|a, b| b.seniority_rank.cmp(&a.seniority_rank).then(a.id.cmp(&b.id)));

    let mut result = ReplacementSearch {
        on_duty: None,
        rest_blocked: None,
        consecutive_blocked: None,
    };
    for off in candidates {
        let ctx = day_context.get(&off.id);
        let working = ctx.map(|(s, _)| schedule_working(s)).unwrap_or(false);
        if !working {
            continue;
        }
        let current_band = normalize_shift_band(
            &replacement_shift_for_rules(off, day_context.get(&off.id)),
            bands,
        );
        let status_officer = officer_full_to_status(off);
        if current_band != covered_band
            && enforce_minimum_rest
            && !meets_minimum_rest(
                &status_officer,
                &off.shift_end,
                request_ordinal,
                shift_start,
                &shift_end_for(shift_start, shift_times),
                maps,
                base_ordinal,
                schedule,
                shift_times,
                covering_shifts,
                min_rest_hours,
            )
        {
            result.rest_blocked = result.rest_blocked.or(Some((*off).clone()));
            continue;
        }
        if enforce_consecutive_work
            && exceeds_consecutive_work_limit(
                &status_officer,
                request_ordinal,
                false,
                max_consecutive_work_days,
                base_ordinal,
                schedule,
                maps,
            )
        {
            result.consecutive_blocked = result.consecutive_blocked.or(Some((*off).clone()));
            continue;
        }
        result.on_duty = result.on_duty.or(Some((*off).clone()));
    }
    result
}

fn night_minimum_uncovered(
    request_date: &str,
    squad: &str,
    shift_start: &str,
    officers: &[Officer],
    overrides_on_date: &[(i64, Option<i64>, Option<String>, String)],
    shift_starts: &[String],
    base_ordinal: i32,
    schedule: &RotationSchedule,
    night_minimum: i32,
) -> bool {
    if !is_high_risk_night_ordinal(parse_ymd(request_date).unwrap_or(0)) || !is_night_shift(shift_start) {
        return false;
    }
    let override_rows: Vec<(String, i64, Option<i64>, Option<String>)> = overrides_on_date
        .iter()
        .map(|(o, r, c, _)| (request_date.to_string(), *o, *r, c.clone()))
        .collect();
    let counts = compute_shift_coverage_counts(
        officers,
        &override_rows,
        request_date,
        request_date,
        shift_starts,
        base_ordinal,
        schedule,
    )
    .unwrap_or_default();
    let current = counts
        .get(&(request_date.to_string(), squad.to_string(), shift_start.to_string()))
        .copied()
        .unwrap_or(0);
    current <= night_minimum
}

pub fn suggest_bump_chain_py(
    py: Python<'_>,
    officers: Vec<OfficerFull>,
    overrides_on_date: &[(i64, Option<i64>, Option<String>, String)],
    original_officer_id: i64,
    request_date: &str,
    squad: &str,
    shift_start: &str,
    bump_rules: HashMap<String, Vec<String>>,
    shift_times: Vec<(String, String)>,
    day_context: HashMap<i64, (String, String)>,
    night_minimum: i32,
    min_rest_hours: f64,
    max_consecutive_work_days: i32,
    covering_shifts: CoveringShiftStarts,
    base_ordinal: i32,
    schedule: RotationSchedule,
    max_assignments_before_busy: i32,
    max_depth: usize,
    enforce_minimum_rest: bool,
    enforce_consecutive_work: bool,
) -> PyResult<PyObject> {
    let mut maps = OverrideMaps {
        bumped: HashMap::new(),
        covering: HashMap::new(),
        swapped: HashMap::new(),
        bumped_status: HashMap::new(),
    };
    for (orig, repl, _cov, reason) in overrides_on_date {
        maps.bumped
            .entry(request_date.to_string())
            .or_default()
            .insert(*orig);
        if reason == "Shift Swap" {
            maps.swapped
                .entry(request_date.to_string())
                .or_default()
                .insert(*orig);
            if let Some(r) = repl {
                maps.swapped.entry(request_date.to_string()).or_default().insert(*r);
            }
            continue;
        }
        if let Some(r) = repl {
            maps.covering
                .entry(request_date.to_string())
                .or_default()
                .insert(*r);
        }
    }

    let mut assignment_counts: HashMap<i64, i32> = HashMap::new();
    for (_orig, repl, _cov, _reason) in overrides_on_date {
        if let Some(r) = repl {
            *assignment_counts.entry(*r).or_insert(0) += 1;
        }
    }

    let mut chain: Vec<(i64, i64)> = Vec::new();
    let mut steps: Vec<PyObject> = Vec::new();
    let mut current_id = original_officer_id;
    let mut current_shift = shift_start.to_string();
    let shift_starts: Vec<String> = shift_times.iter().map(|(s, _)| s.clone()).collect();
    let shift_bands = shift_bands(&bump_rules);
    let request_ordinal = parse_ymd(request_date).unwrap_or(base_ordinal);
    let officer_rows: Vec<Officer> = officers
        .iter()
        .map(|o| Officer {
            id: o.id,
            squad: o.squad.clone(),
            shift_start: o.shift_start.clone(),
            active: o.active,
            job_title: o.job_title.clone(),
        })
        .collect();

    for _ in 0..max_depth {
        let mut excluded: HashSet<i64> = chain
            .iter()
            .flat_map(|(orig, repl)| [*orig, *repl])
            .collect();
        excluded.insert(original_officer_id);
        let Some(current) = officers.iter().find(|o| o.id == current_id) else {
            return dict_result(
                py,
                false,
                "Officer not found while planning coverage",
                true,
                Some("officer_missing"),
                steps,
                chain,
                None,
            );
        };

        let search = find_replacement(
            squad,
            &current_shift,
            &officers,
            &assignment_counts,
            max_assignments_before_busy,
            &bump_rules,
            &day_context,
            &excluded,
            &shift_bands,
            request_ordinal,
            base_ordinal,
            &schedule,
            &maps,
            &shift_times,
            &covering_shifts,
            min_rest_hours,
            max_consecutive_work_days,
            enforce_minimum_rest,
            enforce_consecutive_work,
        );

        let Some(repl) = search.on_duty else {
            if night_minimum_uncovered(
                request_date,
                squad,
                &current_shift,
                &officer_rows,
                overrides_on_date,
                &shift_starts,
                base_ordinal,
                &schedule,
                night_minimum,
            ) {
                return dict_result(
                    py,
                    false,
                    "Cannot cover shift — would drop night coverage below minimum on a high-risk night",
                    true,
                    Some("night_minimum"),
                    steps,
                    chain,
                    None,
                );
            }
            if chain.is_empty() {
                if let Some(blocked) = search.rest_blocked {
                    let status_officer = officer_full_to_status(&blocked);
                    let msg = minimum_rest_message(
                        &blocked.name,
                        &current_shift,
                        &shift_times,
                        request_ordinal,
                        &status_officer,
                        &blocked.shift_end,
                        &maps,
                        base_ordinal,
                        &schedule,
                        &covering_shifts,
                        min_rest_hours,
                    );
                    return dict_result(
                        py,
                        false,
                        &msg,
                        true,
                        Some("minimum_rest"),
                        steps,
                        chain,
                        None,
                    );
                }
                if let Some(blocked) = search.consecutive_blocked {
                    let status_officer = officer_full_to_status(&blocked);
                    let msg = consecutive_work_message(
                        &blocked.name,
                        request_ordinal,
                        false,
                        max_consecutive_work_days,
                        &status_officer,
                        base_ordinal,
                        &schedule,
                        &maps,
                    );
                    return dict_result(
                        py,
                        false,
                        &msg,
                        true,
                        Some("consecutive_days"),
                        steps,
                        chain,
                        None,
                    );
                }
                return dict_result(
                    py,
                    false,
                    "No replacement available on an allowed shift",
                    true,
                    Some("no_replacement"),
                    steps,
                    chain,
                    None,
                );
            }
            let coverage_excluded: HashSet<i64> = chain
                .iter()
                .flat_map(|(orig, repl_id)| [*orig, *repl_id])
                .chain(std::iter::once(original_officer_id))
                .collect();
            if shift_retains_coverage_after_bump(
                current_id,
                &current_shift,
                squad,
                &officers,
                &day_context,
                &coverage_excluded,
                &shift_bands,
            ) {
                let primary_name = officers
                    .iter()
                    .find(|o| o.id == chain[0].1)
                    .map(|o| o.name.as_str());
                let msg = format!("Auto-approve ready — {} assignment(s)", chain.len());
                return dict_result(py, true, &msg, false, None, steps, chain, primary_name);
            }
            let msg = format!(
                "Cascade incomplete — no cover for {}'s {} shift after earlier assignments",
                current.name, current_shift
            );
            return dict_result(
                py,
                false,
                &msg,
                true,
                Some("cascade_incomplete"),
                steps,
                chain,
                None,
            );
        };

        let ctx = day_context.get(&repl.id);
        let on_duty = ctx.map(|(s, _)| schedule_working(s)).unwrap_or(false);
        let repl_shift = ctx
            .and_then(|(_, assigned)| if assigned.is_empty() { None } else { Some(assigned.clone()) })
            .unwrap_or_else(|| repl.shift_start.clone());

        let step = PyDict::new_bound(py);
        step.set_item("step_number", steps.len() + 1)?;
        step.set_item("original_officer_id", current_id)?;
        step.set_item("original_officer_name", &current.name)?;
        step.set_item("original_shift", &current_shift)?;
        step.set_item("replacement_officer_id", repl.id)?;
        step.set_item("replacement_officer_name", &repl.name)?;
        step.set_item("replacement_shift", &repl_shift)?;
        step.set_item("replacement_on_duty", on_duty)?;
        steps.push(step.into());

        chain.push((current_id, repl.id));
        *assignment_counts.entry(repl.id).or_insert(0) += 1;

        let coverage_excluded: HashSet<i64> = chain
            .iter()
            .flat_map(|(orig, repl_id)| [*orig, *repl_id])
            .chain(std::iter::once(original_officer_id))
            .collect();
        if shift_retains_coverage_after_bump(
            repl.id,
            &repl_shift,
            squad,
            &officers,
            &day_context,
            &coverage_excluded,
            &shift_bands,
        ) {
            let primary_name = officers
                .iter()
                .find(|o| o.id == chain[0].1)
                .map(|o| o.name.as_str());
            let msg = format!("Auto-approve ready — {} assignment(s)", chain.len());
            return dict_result(py, true, &msg, false, None, steps, chain, primary_name);
        }

        current_id = repl.id;
        current_shift = repl_shift;
    }

    dict_result(
        py,
        false,
        "Coverage chain too deep — supervisor must assign manually",
        true,
        Some("cascade_too_deep"),
        steps,
        chain,
        None,
    )
}

fn dict_result(
    py: Python<'_>,
    success: bool,
    message: &str,
    requires_manual: bool,
    failure_reason: Option<&str>,
    steps: Vec<PyObject>,
    chain: Vec<(i64, i64)>,
    primary_name: Option<&str>,
) -> PyResult<PyObject> {
    let d = PyDict::new_bound(py);
    d.set_item("success", success)?;
    d.set_item("message", message)?;
    d.set_item("requires_manual", requires_manual)?;
    if let Some(r) = failure_reason {
        d.set_item("failure_reason", r)?;
    }
    let steps_list = PyList::empty_bound(py);
    for s in steps {
        steps_list.append(s)?;
    }
    d.set_item("steps", steps_list)?;
    let chain_list = PyList::empty_bound(py);
    for (a, b) in chain {
        let pair = PyList::empty_bound(py);
        pair.append(a)?;
        pair.append(b)?;
        chain_list.append(pair)?;
    }
    d.set_item("chain", chain_list)?;
    if let Some(name) = primary_name {
        d.set_item("primary_replacement_name", name)?;
    }
    Ok(d.into())
}
