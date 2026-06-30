use std::collections::{HashMap, HashSet};

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use crate::coverage::compute_shift_coverage_counts;
use crate::rotation::{is_high_risk_night_ordinal, parse_ymd, shift_number};
use crate::status::{Officer, OverrideMaps, officer_day_status, officer_working_on_day};

#[derive(Clone)]
pub struct OfficerFull {
    pub id: i64,
    pub name: String,
    pub squad: String,
    pub shift_start: String,
    pub shift_end: String,
    pub active: bool,
}

fn is_night_shift(shift_start: &str) -> bool {
    let hour: i32 = shift_start
        .split(':')
        .next()
        .and_then(|h| h.parse().ok())
        .unwrap_or(12);
    hour >= 18 || hour < 6
}

fn shift_end_for(start: &str, shift_times: &[(String, String)]) -> String {
    for (s, e) in shift_times {
        if s == start {
            return e.clone();
        }
    }
    start.to_string()
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

fn rest_gap_hours(
    officer_id: i64,
    assignment_ordinal: i32,
    new_start: &str,
    new_end: &str,
    officers: &[OfficerFull],
    maps: &OverrideMaps,
    base_ordinal: i32,
    cycle_length: i32,
    shift_times: &[(String, String)],
) -> Option<f64> {
    let officer = officers.iter().find(|o| o.id == officer_id)?;
    let new_start_min = parse_minutes(new_start);
    let new_end_min = parse_minutes(new_end);
    let mut min_gap: Option<f64> = None;

    for delta in [-1i32, 1] {
        let adj_ord = assignment_ordinal + delta;
        let date_key = crate::status::ordinal_to_iso_public(adj_ord);
        let status = officer_day_status(
            &Officer {
                id: officer.id,
                squad: officer.squad.clone(),
                shift_start: officer.shift_start.clone(),
                active: officer.active,
            },
            &date_key,
            adj_ord,
            base_ordinal,
            cycle_length,
            maps,
        );
        if !matches!(status.as_str(), "working" | "covering" | "swapped") {
            continue;
        }
        let mut band_start = officer.shift_start.clone();
        if status == "covering" {
            band_start = officer.shift_start.clone();
        }
        let band_end = shift_end_for(&band_start, shift_times);
        let adj_start = parse_minutes(&band_start);
        let adj_end = parse_minutes(&band_end);

        let gap = if delta == -1 {
            let new_start_abs = assignment_ordinal * 1440 + new_start_min;
            let adj_end_abs = adj_ord * 1440 + if adj_end <= adj_start { adj_end + 1440 } else { adj_end };
            (new_start_abs - adj_end_abs) as f64 / 60.0
        } else {
            let adj_start_abs = adj_ord * 1440 + adj_start;
            let new_end_abs = assignment_ordinal * 1440
                + if new_end_min <= new_start_min {
                    new_end_min + 1440
                } else {
                    new_end_min
                };
            (adj_start_abs - new_end_abs) as f64 / 60.0
        };
        min_gap = Some(min_gap.map_or(gap, |g| g.min(gap)));
    }
    min_gap
}

fn find_replacement(
    original_id: i64,
    request_date: &str,
    squad: &str,
    shift_start: &str,
    officers: &[OfficerFull],
    busy: &HashSet<i64>,
    bump_rules: &HashMap<i32, Vec<i32>>,
    shift_times: &[(String, String)],
    maps: &OverrideMaps,
    base_ordinal: i32,
    cycle_length: i32,
    min_rest_hours: f64,
) -> Option<OfficerFull> {
    let shift_num = shift_number(shift_start, shift_times);
    let allowed: HashSet<i32> = bump_rules
        .get(&shift_num)
        .cloned()
        .unwrap_or_else(|| vec![1, 2, 3, 4])
        .into_iter()
        .collect();

    let req_ord = parse_ymd(request_date).ok()?;
    let coverage_end = shift_end_for(shift_start, shift_times);

    let mut candidates: Vec<&OfficerFull> = officers
        .iter()
        .filter(|o| {
            o.active
                && o.squad == squad
                && o.id != original_id
                && !busy.contains(&o.id)
                && allowed.contains(&shift_number(&o.shift_start, shift_times))
        })
        .collect();
    candidates.sort_by_key(|o| o.id);

    let mut on_duty = None;
    let mut off_rest_ok = None;
    let mut off_rest_bad = None;

    for off in candidates {
        if officer_working_on_day(
            &Officer {
                id: off.id,
                squad: off.squad.clone(),
                shift_start: off.shift_start.clone(),
                active: off.active,
            },
            req_ord,
            base_ordinal,
            cycle_length,
        ) {
            on_duty = on_duty.or(Some((*off).clone()));
        } else {
            let gap = rest_gap_hours(
                off.id,
                req_ord,
                shift_start,
                &coverage_end,
                officers,
                maps,
                base_ordinal,
                cycle_length,
                shift_times,
            );
            if gap.map_or(false, |g| g >= min_rest_hours) {
                off_rest_ok = off_rest_ok.or(Some((*off).clone()));
            } else {
                off_rest_bad = off_rest_bad.or(Some((*off).clone()));
            }
        }
    }
    on_duty.or(off_rest_ok).or(off_rest_bad)
}

pub fn suggest_bump_chain_py(
    py: Python<'_>,
    officers: Vec<OfficerFull>,
    overrides_on_date: &[(i64, Option<i64>, Option<String>, String)],
    original_officer_id: i64,
    request_date: &str,
    squad: &str,
    shift_start: &str,
    bump_rules: HashMap<i32, Vec<i32>>,
    shift_times: Vec<(String, String)>,
    night_minimum: i32,
    min_rest_hours: f64,
    base_ordinal: i32,
    cycle_length: i32,
    max_depth: usize,
) -> PyResult<PyObject> {
    let req_ord = parse_ymd(request_date)?;

    if is_high_risk_night_ordinal(req_ord) && is_night_shift(shift_start) {
        let shift_starts: Vec<String> = shift_times.iter().map(|(s, _)| s.clone()).collect();
        let override_rows: Vec<(String, i64, Option<i64>, Option<String>)> = overrides_on_date
            .iter()
            .map(|(o, r, c, _)| (request_date.to_string(), *o, *r, c.clone()))
            .collect();
        let officer_rows: Vec<Officer> = officers
            .iter()
            .map(|o| Officer {
                id: o.id,
                squad: o.squad.clone(),
                shift_start: o.shift_start.clone(),
                active: o.active,
            })
            .collect();
        let counts = compute_shift_coverage_counts(
            &officer_rows,
            &override_rows,
            request_date,
            request_date,
            &shift_starts,
            base_ordinal,
            cycle_length,
        )?;
        let current = counts
            .get(&(request_date.to_string(), squad.to_string(), shift_start.to_string()))
            .copied()
            .unwrap_or(0);
        if current <= night_minimum {
            return dict_result(
                py,
                false,
                "Would drop night coverage below minimum on a high-risk night",
                true,
                Some("night_minimum"),
                vec![],
                vec![],
                None,
            );
        }
    }

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

    let mut chain: Vec<(i64, i64)> = Vec::new();
    let mut steps: Vec<PyObject> = Vec::new();
    let mut busy: HashSet<i64> = HashSet::from([original_officer_id]);
    let mut current_id = original_officer_id;
    let mut current_squad = squad.to_string();
    let mut current_shift = shift_start.to_string();

    for _ in 0..max_depth {
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

        let replacement = find_replacement(
            current_id,
            request_date,
            &current_squad,
            &current_shift,
            &officers,
            &busy,
            &bump_rules,
            &shift_times,
            &maps,
            base_ordinal,
            cycle_length,
            min_rest_hours,
        );

        let Some(repl) = replacement else {
            if chain.is_empty() {
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

        let on_duty = officer_working_on_day(
            &Officer {
                id: repl.id,
                squad: repl.squad.clone(),
                shift_start: repl.shift_start.clone(),
                active: repl.active,
            },
            req_ord,
            base_ordinal,
            cycle_length,
        );

        let step = PyDict::new_bound(py);
        step.set_item("step_number", steps.len() + 1)?;
        step.set_item("original_officer_id", current_id)?;
        step.set_item("original_officer_name", &current.name)?;
        step.set_item("original_shift", &current_shift)?;
        step.set_item("replacement_officer_id", repl.id)?;
        step.set_item("replacement_officer_name", &repl.name)?;
        step.set_item("replacement_shift", &repl.shift_start)?;
        step.set_item("replacement_on_duty", on_duty)?;
        steps.push(step.into());

        chain.push((current_id, repl.id));
        busy.insert(repl.id);

        if !on_duty {
            let coverage_end = shift_end_for(&current_shift, &shift_times);
            let gap = rest_gap_hours(
                repl.id,
                req_ord,
                &current_shift,
                &coverage_end,
                &officers,
                &maps,
                base_ordinal,
                cycle_length,
                &shift_times,
            );
            let primary_name = officers
                .iter()
                .find(|o| o.id == chain[0].1)
                .map(|o| o.name.as_str());
            if gap.map_or(true, |g| g < min_rest_hours) {
                let msg = format!(
                    "Minimum rest violation: {} has {:.1}h between shifts (minimum {:.0}h) — supervisor override required",
                    repl.name,
                    gap.unwrap_or(0.0),
                    min_rest_hours
                );
                return dict_result(
                    py,
                    false,
                    &msg,
                    true,
                    Some("minimum_rest"),
                    steps,
                    chain,
                    primary_name,
                );
            }
            let msg = format!("Auto-approve ready — {} assignment(s)", chain.len());
            return dict_result(py, true, &msg, false, None, steps, chain, primary_name);
        }

        current_id = repl.id;
        current_squad = repl.squad.clone();
        current_shift = repl.shift_start.clone();
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
