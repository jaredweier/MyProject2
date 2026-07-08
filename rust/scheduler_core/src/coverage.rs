use std::collections::{HashMap, HashSet};

use pyo3::prelude::*;

use crate::rotation::{cycle_day, RotationSchedule};
use crate::status::{officer_base_rotation_working, Officer};

fn parse_minutes(value: &str) -> i32 {
    let parts: Vec<&str> = value.split(':').collect();
    if parts.len() < 2 {
        return 0;
    }
    let h: i32 = parts[0].parse().unwrap_or(0);
    let m: i32 = parts[1].parse().unwrap_or(0);
    h * 60 + m
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

pub fn compute_shift_coverage_counts(
    officers: &[Officer],
    overrides: &[(String, i64, Option<i64>, Option<String>)],
    start: &str,
    end: &str,
    shift_starts: &[String],
    base_ordinal: i32,
    schedule: &RotationSchedule,
) -> PyResult<HashMap<(String, String, String), i32>> {
    let start_ord = crate::rotation::parse_ymd(start)?;
    let end_ord = crate::rotation::parse_ymd(end)?;

    let mut bumped_by_date: HashMap<String, HashSet<i64>> = HashMap::new();
    let mut replacements_by_date: HashMap<String, Vec<(i64, Option<String>)>> = HashMap::new();

    for (day, orig, repl, covered) in overrides {
        if day.as_str() >= start && day.as_str() <= end {
            bumped_by_date.entry(day.clone()).or_default().insert(*orig);
            if let Some(rid) = repl {
                replacements_by_date
                    .entry(day.clone())
                    .or_default()
                    .push((*rid, covered.clone()));
            }
        }
    }

    let active: Vec<&Officer> = officers.iter().filter(|o| o.active).collect();
    let mut counts: HashMap<(String, String, String), i32> = HashMap::new();

    let mut ord = start_ord;
    while ord <= end_ord {
        let day_str = crate::status::ordinal_to_iso_public(ord);
        let bumped = bumped_by_date.get(&day_str).cloned().unwrap_or_default();

        let cycle_day = cycle_day(base_ordinal, ord, schedule.cycle_length);
        let squad_on_duty = schedule.squad_on_duty(cycle_day);
        for squad in ["A", "B"] {
            for shift_start in shift_starts {
                let base = if squad != squad_on_duty {
                    0
                } else {
                    active
                        .iter()
                        .filter(|o| {
                            o.squad == squad
                                && normalize_shift_band(&o.shift_start, shift_starts) == *shift_start
                                && !bumped.contains(&o.id)
                                && officer_base_rotation_working(o, ord, base_ordinal, schedule)
                        })
                        .count() as i32
                };

                let mut repl = 0;
                let mut seen: HashSet<i64> = HashSet::new();
                if let Some(rows) = replacements_by_date.get(&day_str) {
                    for (rid, covered) in rows {
                        if seen.contains(rid) {
                            continue;
                        }
                        let Some(off) = active.iter().find(|o| o.id == *rid) else {
                            continue;
                        };
                        if off.squad != squad {
                            continue;
                        }
                        let effective = covered.as_deref().unwrap_or(off.shift_start.as_str());
                        if normalize_shift_band(effective, shift_starts) == *shift_start {
                            seen.insert(*rid);
                            repl += 1;
                        }
                    }
                }
                counts.insert((day_str.clone(), squad.to_string(), shift_start.clone()), base + repl);
            }
        }
        ord += 1;
    }
    Ok(counts)
}
