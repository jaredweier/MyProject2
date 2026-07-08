use std::collections::HashMap;

use crate::rotation::RotationSchedule;
use crate::status::{officer_day_status, Officer, OverrideMaps};

pub const WORKING_STATUSES: &[&str] = &["working", "covering", "swapped", "training"];

pub fn is_working_status(status: &str) -> bool {
    WORKING_STATUSES.contains(&status)
}

/// Count consecutive scheduled work days ending on end_ordinal (inclusive).
pub fn consecutive_work_days_ending(
    officer: &Officer,
    end_ordinal: i32,
    base_ordinal: i32,
    schedule: &RotationSchedule,
    maps: &OverrideMaps,
    max_lookback: i32,
) -> i32 {
    let mut count = 0;
    let mut current = end_ordinal;
    for _ in 0..max_lookback {
        let date_key = crate::status::ordinal_to_iso_public(current);
        let status = officer_day_status(officer, &date_key, current, base_ordinal, schedule, maps);
        if !is_working_status(status.as_str()) {
            break;
        }
        count += 1;
        current -= 1;
    }
    count
}

/// True when assignment would exceed the consecutive-work-day cap.
pub fn exceeds_consecutive_work_limit(
    officer: &Officer,
    assignment_ordinal: i32,
    adding_work_day: bool,
    max_days: i32,
    base_ordinal: i32,
    schedule: &RotationSchedule,
    maps: &OverrideMaps,
) -> bool {
    if adding_work_day {
        let prior = consecutive_work_days_ending(
            officer,
            assignment_ordinal - 1,
            base_ordinal,
            schedule,
            maps,
            20,
        );
        return prior + 1 > max_days;
    }
    consecutive_work_days_ending(officer, assignment_ordinal, base_ordinal, schedule, maps, 20)
        > max_days
}

pub fn consecutive_work_message(
    officer_name: &str,
    assignment_ordinal: i32,
    adding_work_day: bool,
    max_days: i32,
    officer: &Officer,
    base_ordinal: i32,
    schedule: &RotationSchedule,
    maps: &OverrideMaps,
) -> String {
    let streak = if adding_work_day {
        consecutive_work_days_ending(
            officer,
            assignment_ordinal - 1,
            base_ordinal,
            schedule,
            maps,
            20,
        ) + 1
    } else {
        consecutive_work_days_ending(
            officer,
            assignment_ordinal,
            base_ordinal,
            schedule,
            maps,
            20,
        )
    };
    format!(
        "Consecutive work day limit: {} would reach {} days (maximum {}) — supervisor override required",
        officer_name, streak, max_days
    )
}

/// Per-date covered shift start for replacements (date -> officer_id -> HH:MM).
pub type CoveringShiftStarts = HashMap<String, HashMap<i64, String>>;
