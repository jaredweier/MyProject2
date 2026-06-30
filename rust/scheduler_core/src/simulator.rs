use std::collections::HashMap;

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use crate::rotation::is_high_risk_night_ordinal;

fn parse_minutes(value: &str) -> i32 {
    let parts: Vec<&str> = value.split(':').collect();
    if parts.len() < 2 {
        return 0;
    }
    parts[0].parse::<i32>().unwrap_or(0) * 60 + parts[1].parse::<i32>().unwrap_or(0)
}

fn format_minutes(total: i32) -> String {
    let t = total.rem_euclid(24 * 60);
    format!("{:02}:{:02}", t / 60, t % 60)
}

fn shift_end(start: &str, hours: f64) -> String {
    format_minutes(parse_minutes(start) + (hours * 60.0) as i32)
}

fn is_night_shift_start(start: &str) -> bool {
    let hour: i32 = start.split(':').next().and_then(|h| h.parse().ok()).unwrap_or(12);
    hour >= 18 || hour < 6
}

fn squad_working(squad: &str, cycle_day: i32, squad_a_days: &std::collections::HashSet<i32>) -> bool {
    let on_a = squad_a_days.contains(&cycle_day);
    if squad == "A" {
        on_a
    } else {
        !on_a
    }
}

pub fn simulate_schedule_py(
    py: Python<'_>,
    config: &Bound<'_, PyDict>,
    preset: &Bound<'_, PyDict>,
    sim_start_iso: &str,
) -> PyResult<PyObject> {
    let num_officers: i32 = config.get_item("num_officers")?.unwrap().extract()?;
    let shift_length_hours: f64 = config.get_item("shift_length_hours")?.unwrap().extract()?;
    let simulation_days: i32 = config.get_item("simulation_days")?.unwrap().extract()?;
    let min_per_shift: i32 = config.get_item("min_per_shift")?.unwrap().extract()?;
    let apply_rules: bool = config
        .get_item("apply_department_rules")?
        .unwrap()
        .extract()
        .unwrap_or(true);
    let annual_target: f64 = config.get_item("annual_hours_target")?.unwrap().extract()?;
    let night_minimum: i32 = config.get_item("night_minimum")?.unwrap().extract()?;
    let squad_a_days: std::collections::HashSet<i32> = config
        .get_item("squad_a_days")?
        .unwrap()
        .extract()?;

    let templates: Vec<(String, String)> = config
        .get_item("shift_templates")?
        .unwrap()
        .extract()?;

    let cycle_length: i32 = preset.get_item("cycle_length")?.unwrap().extract()?;
    let start_ord = crate::rotation::parse_ymd(sim_start_iso)?;

    let squads = if preset.get_item("squads")?.unwrap().extract::<i32>().unwrap_or(2) >= 2 {
        vec!["A", "B"]
    } else {
        vec!["A"]
    };

    let mut slots: Vec<(i32, String, String, String, String)> = Vec::new();
    for i in 0..num_officers {
        let squad = squads[(i as usize) % squads.len()].to_string();
        let (ss, se) = &templates[(i as usize) % templates.len()];
        slots.push((i + 1, format!("Officer {}", i + 1), squad, ss.clone(), se.clone()));
    }

    let mut gap_counter: HashMap<(i32, String), i32> = HashMap::new();
    let mut coverage_by_day = PyList::empty_bound(py);
    let mut min_coverage = 999;
    let mut max_coverage = 0;

    for day_offset in 0..simulation_days {
        let ord = start_ord + day_offset;
        let cycle_day = (day_offset % cycle_length) + 1;
        let mut shift_counts: HashMap<String, i32> = HashMap::new();
        for (s, _) in &templates {
            shift_counts.insert(s.clone(), 0);
        }
        let mut working = 0;
        for slot in &mut slots {
            if squad_working(&slot.2, cycle_day, &squad_a_days) {
                working += 1;
                *shift_counts.entry(slot.3.clone()).or_insert(0) += 1;
            }
        }
        let day_min = shift_counts.values().copied().min().unwrap_or(0);
        let day_max = shift_counts.values().copied().max().unwrap_or(0);
        min_coverage = min_coverage.min(day_min);
        max_coverage = max_coverage.max(day_max);

        for (shift_start, count) in &shift_counts {
            let mut required = min_per_shift;
            if apply_rules && is_night_shift_start(shift_start) && is_high_risk_night_ordinal(ord) {
                required = required.max(night_minimum);
            }
            if *count < required {
                let gap = required - count;
                gap_counter.insert((day_offset, shift_start.clone()), gap);
            }
        }

        let day_dict = PyDict::new_bound(py);
        day_dict.set_item("date", crate::status::ordinal_to_iso_public(ord))?;
        day_dict.set_item("cycle_day", cycle_day)?;
        day_dict.set_item("shift_counts", shift_counts)?;
        day_dict.set_item("working_officers", working)?;
        day_dict.set_item("min_shift_coverage", day_min)?;
        day_dict.set_item("high_risk_night", is_high_risk_night_ordinal(ord))?;
        coverage_by_day.append(day_dict)?;
    }

    let slots_per_day = templates.len() as i32;
    let weekly = 24 * 7 * min_per_shift;
    let fte_required = (weekly as f64 * 52.0) / annual_target.max(1.0);

    let metrics = PyDict::new_bound(py);
    let coverage_pct = if gap_counter.is_empty() {
        100.0
    } else {
        let total_required = simulation_days * slots_per_day * min_per_shift;
        let total_met = total_required - gap_counter.values().sum::<i32>();
        100.0 * total_met as f64 / total_required.max(1) as f64
    };
    metrics.set_item("coverage_percent", (coverage_pct * 10.0).round() / 10.0)?;
    metrics.set_item("min_shift_coverage", if min_coverage == 999 { 0 } else { min_coverage })?;
    metrics.set_item("max_shift_coverage", max_coverage)?;
    metrics.set_item("fte_required", (fte_required * 100.0).round() / 100.0)?;
    metrics.set_item("gap_events", gap_counter.len())?;
    metrics.set_item("shifts_per_day", slots_per_day)?;

    let result = PyDict::new_bound(py);
    result.set_item("success", true)?;
    result.set_item("message", "Simulation complete")?;
    result.set_item("shift_templates", templates)?;
    result.set_item("coverage_by_day", coverage_by_day)?;
    result.set_item("metrics", metrics)?;
    Ok(result.into())
}
