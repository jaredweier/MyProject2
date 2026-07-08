use crate::compliance::CoveringShiftStarts;
use crate::rotation::RotationSchedule;
use crate::status::{officer_day_status, Officer, OverrideMaps};

pub fn parse_minutes(value: &str) -> i32 {
    let parts: Vec<&str> = value.split(':').collect();
    if parts.len() < 2 {
        return 0;
    }
    let h: i32 = parts[0].parse().unwrap_or(0);
    let m: i32 = parts[1].parse().unwrap_or(0);
    h * 60 + m
}

pub fn shift_end_for(start: &str, shift_times: &[(String, String)]) -> String {
    for (s, e) in shift_times {
        if s == start {
            return e.clone();
        }
    }
    start.to_string()
}

fn effective_band_start(
    officer: &Officer,
    date_key: &str,
    status: &str,
    covering_shifts: &CoveringShiftStarts,
) -> String {
    if status == "covering" {
        if let Some(day_map) = covering_shifts.get(date_key) {
            if let Some(start) = day_map.get(&officer.id) {
                if !start.is_empty() {
                    return start.clone();
                }
            }
        }
    }
    officer.shift_start.clone()
}

/// Hours between a new assignment and nearest adjacent working day (None if no adjacent work).
pub fn minimum_rest_gap_hours(
    officer: &Officer,
    officer_shift_end: &str,
    assignment_ordinal: i32,
    new_start: &str,
    new_end: &str,
    maps: &OverrideMaps,
    base_ordinal: i32,
    schedule: &RotationSchedule,
    covering_shifts: &CoveringShiftStarts,
) -> Option<f64> {
    let new_start_min = parse_minutes(new_start);
    let new_end_min = parse_minutes(new_end);
    let mut min_gap: Option<f64> = None;

    for delta in [-1i32, 1] {
        let adj_ord = assignment_ordinal + delta;
        let date_key = crate::status::ordinal_to_iso_public(adj_ord);
        let status = officer_day_status(officer, &date_key, adj_ord, base_ordinal, schedule, maps);
        if !matches!(status.as_str(), "working" | "covering" | "swapped") {
            continue;
        }
        let band_start = effective_band_start(officer, &date_key, &status, covering_shifts);
        let band_end = if status == "covering" {
            shift_end_for(&band_start, &[])
        } else if officer_shift_end.is_empty() {
            band_start.clone()
        } else {
            officer_shift_end.to_string()
        };
        let adj_start = parse_minutes(&band_start);
        let adj_end = parse_minutes(&band_end);

        let gap = if delta == -1 {
            let new_start_abs = assignment_ordinal * 1440 + new_start_min;
            let adj_end_abs =
                adj_ord * 1440 + if adj_end <= adj_start { adj_end + 1440 } else { adj_end };
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

pub fn minimum_rest_gap_hours_with_times(
    officer: &Officer,
    officer_shift_end: &str,
    assignment_ordinal: i32,
    new_start: &str,
    new_end: &str,
    maps: &OverrideMaps,
    base_ordinal: i32,
    schedule: &RotationSchedule,
    shift_times: &[(String, String)],
    covering_shifts: &CoveringShiftStarts,
) -> Option<f64> {
    let new_start_min = parse_minutes(new_start);
    let new_end_min = parse_minutes(new_end);
    let mut min_gap: Option<f64> = None;

    for delta in [-1i32, 1] {
        let adj_ord = assignment_ordinal + delta;
        let date_key = crate::status::ordinal_to_iso_public(adj_ord);
        let status = officer_day_status(officer, &date_key, adj_ord, base_ordinal, schedule, maps);
        if !matches!(status.as_str(), "working" | "covering" | "swapped") {
            continue;
        }
        let band_start = effective_band_start(officer, &date_key, &status, covering_shifts);
        let band_end = if status == "covering" {
            shift_end_for(&band_start, shift_times)
        } else if officer_shift_end.is_empty() {
            shift_end_for(&band_start, shift_times)
        } else {
            officer_shift_end.to_string()
        };
        let adj_start = parse_minutes(&band_start);
        let adj_end = parse_minutes(&band_end);

        let gap = if delta == -1 {
            let new_start_abs = assignment_ordinal * 1440 + new_start_min;
            let adj_end_abs =
                adj_ord * 1440 + if adj_end <= adj_start { adj_end + 1440 } else { adj_end };
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

pub fn meets_minimum_rest(
    officer: &Officer,
    officer_shift_end: &str,
    assignment_ordinal: i32,
    covered_start: &str,
    covered_end: &str,
    maps: &OverrideMaps,
    base_ordinal: i32,
    schedule: &RotationSchedule,
    shift_times: &[(String, String)],
    covering_shifts: &CoveringShiftStarts,
    min_rest_hours: f64,
) -> bool {
    match minimum_rest_gap_hours_with_times(
        officer,
        officer_shift_end,
        assignment_ordinal,
        covered_start,
        covered_end,
        maps,
        base_ordinal,
        schedule,
        shift_times,
        covering_shifts,
    ) {
        None => true,
        Some(gap) => gap >= min_rest_hours,
    }
}

pub fn minimum_rest_message(
    officer_name: &str,
    covered_start: &str,
    shift_times: &[(String, String)],
    request_ordinal: i32,
    officer: &Officer,
    officer_shift_end: &str,
    maps: &OverrideMaps,
    base_ordinal: i32,
    schedule: &RotationSchedule,
    covering_shifts: &CoveringShiftStarts,
    min_rest_hours: f64,
) -> String {
    let covered_end = shift_end_for(covered_start, shift_times);
    let gap = minimum_rest_gap_hours_with_times(
        officer,
        officer_shift_end,
        request_ordinal,
        covered_start,
        &covered_end,
        maps,
        base_ordinal,
        schedule,
        shift_times,
        covering_shifts,
    );
    let gap_text = gap
        .map(|g| format!("{:.1}h", g))
        .unwrap_or_else(|| "insufficient rest".to_string());
    format!(
        "Minimum rest violation: {} has {} between shifts (minimum {:.0}h required) — supervisor override required",
        officer_name, gap_text, min_rest_hours
    )
}
