use pyo3::prelude::*;

const SQUAD_A_DAYS: [u8; 7] = [1, 2, 5, 6, 7, 10, 11];

pub fn parse_ymd(value: &str) -> PyResult<i32> {
    let parts: Vec<&str> = value.split('-').collect();
    if parts.len() != 3 {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "invalid date: {value}"
        )));
    }
    let y: i32 = parts[0].parse().map_err(|_| {
        pyo3::exceptions::PyValueError::new_err(format!("invalid year in {value}"))
    })?;
    let m: u32 = parts[1].parse().map_err(|_| {
        pyo3::exceptions::PyValueError::new_err(format!("invalid month in {value}"))
    })?;
    let d: u32 = parts[2].parse().map_err(|_| {
        pyo3::exceptions::PyValueError::new_err(format!("invalid day in {value}"))
    })?;
    Ok(ymd_to_ordinal(y, m, d))
}

fn ymd_to_ordinal(year: i32, month: u32, day: u32) -> i32 {
    let mut y = year;
    let mut m = month as i32;
    if m <= 2 {
        y -= 1;
        m += 12;
    }
    let era = if y >= 0 { y / 400 } else { (y - 399) / 400 };
    let yoe = y - era * 400;
    let doy = (153 * (m - 3) + 2) / 5 + day as i32 - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doe;
    era * 146097 + doe - 719468
}

pub fn ordinal_to_weekday(ordinal: i32) -> u8 {
    ((ordinal + 1).rem_euclid(7)) as u8
}

pub fn is_high_risk_night_ordinal(ordinal: i32) -> bool {
    is_high_risk_night_weekday(ordinal_to_weekday(ordinal))
}

pub fn cycle_day(base_ordinal: i32, target_ordinal: i32, cycle_length: i32) -> i32 {
    let mut diff = target_ordinal - base_ordinal;
    if diff < 0 {
        let cycles = (-diff / cycle_length) + 1;
        diff += cycles * cycle_length;
    }
    (diff % cycle_length) + 1
}

pub fn squad_on_duty(cycle_day: i32) -> &'static str {
    if SQUAD_A_DAYS.contains(&(cycle_day as u8)) {
        "A"
    } else {
        "B"
    }
}

pub fn is_high_risk_night_weekday(weekday: u8) -> bool {
    weekday == 4 || weekday == 5
}

pub fn shift_number(shift_start: &str, shift_times: &[(String, String)]) -> i32 {
    for (idx, (start, _)) in shift_times.iter().enumerate() {
        if start == shift_start {
            return (idx + 1) as i32;
        }
    }
    let hour: i32 = shift_start
        .split(':')
        .next()
        .and_then(|h| h.parse().ok())
        .unwrap_or(0);
    (hour / 6) + 1
}
