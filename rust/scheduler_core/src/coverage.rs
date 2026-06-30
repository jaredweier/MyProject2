use std::collections::{HashMap, HashSet};

use pyo3::prelude::*;

use crate::status::Officer;

pub fn compute_shift_coverage_counts(
    officers: &[Officer],
    overrides: &[(String, i64, Option<i64>, Option<String>)],
    start: &str,
    end: &str,
    shift_starts: &[String],
    base_ordinal: i32,
    cycle_length: i32,
) -> PyResult<HashMap<(String, String, String), i32>> {
    let start_ord = crate::rotation::parse_ymd(start)?;
    let end_ord = crate::rotation::parse_ymd(end)?;

    let mut bumped_by_date: HashMap<String, HashSet<i64>> = HashMap::new();
    let mut replacements_by_date: HashMap<String, Vec<(i64, Option<String>)>> = HashMap::new();

    for (day, orig, repl, covered) in overrides {
        if start <= day && day <= end {
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

        for squad in ["A", "B"] {
            for shift_start in shift_starts {
                let base = active
                    .iter()
                    .filter(|o| {
                        o.squad == squad
                            && o.shift_start == *shift_start
                            && !bumped.contains(&o.id)
                    })
                    .count() as i32;

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
                        if effective == shift_start.as_str() {
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
