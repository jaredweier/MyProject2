use std::collections::{HashMap, HashSet};

use pyo3::prelude::*;

use crate::rotation::{cycle_day, parse_ymd, RotationSchedule};

#[derive(Clone)]
pub struct Officer {
    pub id: i64,
    pub squad: String,
    pub shift_start: String,
    pub active: bool,
    pub job_title: String,
}

const COMMAND_STAFF_TITLES: &[&str] = &["Chief", "Lieutenant"];

pub fn is_command_staff_title(title: &str) -> bool {
    !title.is_empty() && COMMAND_STAFF_TITLES.contains(&title)
}

pub fn weekday_monday_zero(ordinal: i32) -> i32 {
    let iso = ordinal_to_iso(ordinal);
    let parts: Vec<&str> = iso.split('-').collect();
    if parts.len() != 3 {
        return 0;
    }
    let y: i32 = parts[0].parse().unwrap_or(0);
    let m: i32 = parts[1].parse().unwrap_or(1);
    let d: i32 = parts[2].parse().unwrap_or(1);
    let (y, m) = if m < 3 { (y - 1, m + 12) } else { (y, m) };
    let k = y % 100;
    let j = y / 100;
    let h = (d + (13 * (m + 1)) / 5 + k + k / 4 + j / 4 + 5 * j) % 7;
    (h + 5) % 7
}

pub fn officer_base_rotation_working(
    officer: &Officer,
    target_ordinal: i32,
    base_ordinal: i32,
    schedule: &RotationSchedule,
) -> bool {
    if !officer.active {
        return false;
    }
    if is_command_staff_title(&officer.job_title) {
        return weekday_monday_zero(target_ordinal) < 5;
    }
    officer_working_on_day(officer, target_ordinal, base_ordinal, schedule)
}

pub struct OverrideMaps {
    pub bumped: HashMap<String, HashSet<i64>>,
    pub covering: HashMap<String, HashSet<i64>>,
    pub swapped: HashMap<String, HashSet<i64>>,
    pub bumped_status: HashMap<String, HashMap<i64, String>>,
}

pub fn officer_working_on_day(
    officer: &Officer,
    target_ordinal: i32,
    base_ordinal: i32,
    schedule: &RotationSchedule,
) -> bool {
    if !officer.active || officer.squad.is_empty() || officer.shift_start.is_empty() {
        return false;
    }
    let day = cycle_day(base_ordinal, target_ordinal, schedule.cycle_length);
    schedule.is_squad_working(&officer.squad, day)
}

pub fn officer_day_status(
    officer: &Officer,
    date_key: &str,
    target_ordinal: i32,
    base_ordinal: i32,
    schedule: &RotationSchedule,
    maps: &OverrideMaps,
) -> String {
    let id = officer.id;
    if maps
        .swapped
        .get(date_key)
        .map(|s| s.contains(&id))
        .unwrap_or(false)
    {
        return "swapped".to_string();
    }
    if maps.bumped.get(date_key).map(|s| s.contains(&id)).unwrap_or(false) {
        if let Some(statuses) = maps.bumped_status.get(date_key) {
            if let Some(status) = statuses.get(&id) {
                return status.clone();
            }
        }
        return "bumped".to_string();
    }
    if maps
        .covering
        .get(date_key)
        .map(|s| s.contains(&id))
        .unwrap_or(false)
    {
        return "covering".to_string();
    }
    if officer_base_rotation_working(officer, target_ordinal, base_ordinal, schedule) {
        return "working".to_string();
    }
    "off".to_string()
}

pub fn iter_dates(start: &str, end: &str) -> PyResult<Vec<(String, i32)>> {
    let start_ord = parse_ymd(start)?;
    let end_ord = parse_ymd(end)?;
    let mut out = Vec::new();
    let mut ord = start_ord;
    while ord <= end_ord {
        out.push((ordinal_to_iso(ord), ord));
        ord += 1;
    }
    Ok(out)
}

pub fn ordinal_to_iso_public(ordinal: i32) -> String {
    ordinal_to_iso(ordinal)
}

fn ordinal_to_iso(ordinal: i32) -> String {
    let z = ordinal + 719468;
    let era = if z >= 0 { z / 146097 } else { (z - 146096) / 146097 };
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = mp + if mp < 10 { 3 } else { -9 };
    let year = y + if m <= 2 { 1 } else { 0 };
    format!("{year:04}-{m:02}-{d:02}")
}
