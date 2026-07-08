mod bump;
mod compliance;
mod coverage;
mod rest;
mod rotation;
mod simulator;
mod status;

use std::collections::{HashMap, HashSet};

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};

use bump::{OfficerFull, suggest_bump_chain_py};
use compliance::{consecutive_work_days_ending, CoveringShiftStarts};
use coverage::compute_shift_coverage_counts;
use rest::minimum_rest_gap_hours_with_times;
use rotation::{cycle_day, parse_ymd, rotation_schedule_from_py, RotationSchedule};
use status::{
    Officer, OverrideMaps, iter_dates, officer_base_rotation_working, officer_day_status,
};

fn covering_shifts_from_py(py_dict: Option<&Bound<'_, PyDict>>) -> PyResult<CoveringShiftStarts> {
    let mut out: CoveringShiftStarts = HashMap::new();
    let Some(dict) = py_dict else {
        return Ok(out);
    };
    for (day_key, value) in dict.iter() {
        let date_key: String = day_key.extract()?;
        let inner: &Bound<'_, PyDict> = value.downcast()?;
        let mut day_map = HashMap::new();
        for (officer_key, shift_val) in inner.iter() {
            let officer_id: i64 = officer_key.extract()?;
            let shift_start: String = shift_val.extract()?;
            day_map.insert(officer_id, shift_start);
        }
        out.insert(date_key, day_map);
    }
    Ok(out)
}

fn optional_string(dict: &Bound<'_, PyDict>, key: &str) -> String {
    match dict.get_item(key) {
        Ok(Some(v)) => v.extract().unwrap_or_default(),
        _ => String::new(),
    }
}

fn officer_from_py(dict: &Bound<'_, PyDict>) -> PyResult<Officer> {
    Ok(Officer {
        id: dict.get_item("id")?.unwrap().extract()?,
        squad: dict.get_item("squad")?.unwrap().extract()?,
        shift_start: dict.get_item("shift_start")?.unwrap().extract()?,
        active: dict
            .get_item("active")?
            .unwrap()
            .extract()
            .unwrap_or(true),
        job_title: optional_string(dict, "job_title"),
    })
}

#[pyfunction]
fn get_cycle_day(base_date: &str, target_date: &str, cycle_length: i32) -> PyResult<i32> {
    let base = parse_ymd(base_date)?;
    let target = parse_ymd(target_date)?;
    Ok(cycle_day(base, target, cycle_length))
}

#[pyfunction]
#[pyo3(signature = (cycle_day, rotation_schedule=None))]
fn get_squad_on_duty(
    cycle_day: i32,
    rotation_schedule: Option<&Bound<'_, PyDict>>,
) -> PyResult<String> {
    let schedule = match rotation_schedule {
        Some(dict) => rotation_schedule_from_py(dict)?,
        None => RotationSchedule::dodgeville_default(),
    };
    Ok(schedule.squad_on_duty(cycle_day).to_string())
}

#[pyfunction]
fn build_schedule_matrix(
    py: Python<'_>,
    officers: &Bound<'_, PyList>,
    bumped: &Bound<'_, PyDict>,
    covering: &Bound<'_, PyDict>,
    swapped: &Bound<'_, PyDict>,
    bumped_status: &Bound<'_, PyDict>,
    start_date: &str,
    end_date: &str,
    base_date: &str,
    cycle_length: i32,
    rotation_schedule: &Bound<'_, PyDict>,
) -> PyResult<PyObject> {
    let base_ord = parse_ymd(base_date)?;
    let mut schedule = rotation_schedule_from_py(rotation_schedule)?;
    schedule.cycle_length = cycle_length;
    let maps = py_maps_to_rust(bumped, covering, swapped, bumped_status)?;
    let dates = iter_dates(start_date, end_date)?;

    let mut officer_rows: Vec<(PyObject, Officer)> = Vec::new();
    for item in officers.iter() {
        let d: &Bound<'_, PyDict> = item.downcast()?;
        let id: i64 = d.get_item("id")?.unwrap().extract()?;
        let squad: String = d.get_item("squad")?.unwrap().extract()?;
        let shift_start: String = d.get_item("shift_start")?.unwrap().extract()?;
        let active: bool = d.get_item("active")?.unwrap().extract().unwrap_or(true);
        let job_title = optional_string(d, "job_title");
        officer_rows.push((
            item.into(),
            Officer {
                id,
                squad,
                shift_start,
                active,
                job_title,
            },
        ));
    }

    let days_list = PyList::empty_bound(py);
    let matrix_list = PyList::empty_bound(py);

    for (date_key, ord) in &dates {
        days_list.append(date_key)?;
    }

    for (off_py, off) in &officer_rows {
        let day_map = PyDict::new_bound(py);
        for (date_key, ord) in &dates {
            let status = officer_day_status(off, date_key, *ord, base_ord, &schedule, &maps);
            day_map.set_item(date_key, status)?;
        }
        let entry = PyDict::new_bound(py);
        entry.set_item("officer", off_py)?;
        entry.set_item("days", day_map)?;
        matrix_list.append(entry)?;
    }

    let out = PyDict::new_bound(py);
    out.set_item("days", days_list)?;
    out.set_item("matrix", matrix_list)?;
    Ok(out.into())
}

#[pyfunction]
#[pyo3(signature = (officers, bumped, covering, swapped, bumped_status, pairs, base_date, cycle_length, rotation_schedule))]
fn batch_day_status(
    py: Python<'_>,
    officers: &Bound<'_, PyList>,
    bumped: &Bound<'_, PyDict>,
    covering: &Bound<'_, PyDict>,
    swapped: &Bound<'_, PyDict>,
    bumped_status: &Bound<'_, PyDict>,
    pairs: Vec<(i64, String)>,
    base_date: &str,
    cycle_length: i32,
    rotation_schedule: &Bound<'_, PyDict>,
) -> PyResult<PyObject> {
    let base_ord = parse_ymd(base_date)?;
    let mut schedule = rotation_schedule_from_py(rotation_schedule)?;
    schedule.cycle_length = cycle_length;
    let maps = py_maps_to_rust(bumped, covering, swapped, bumped_status)?;

    let mut by_id: HashMap<i64, Officer> = HashMap::new();
    for item in officers.iter() {
        let d: &Bound<'_, PyDict> = item.downcast()?;
        let off = officer_from_py(d)?;
        by_id.insert(off.id, off);
    }

    let out = PyDict::new_bound(py);
    for (officer_id, date_key) in pairs {
        let status = if let Some(off) = by_id.get(&officer_id) {
            let ord = parse_ymd(&date_key)?;
            officer_day_status(off, &date_key, ord, base_ord, &schedule, &maps)
        } else {
            "off".to_string()
        };
        out.set_item((officer_id, date_key), status)?;
    }
    Ok(out.into())
}

#[pyfunction]
#[pyo3(signature = (squad, shift_start, active, job_title, target_date, base_date, cycle_length, rotation_schedule=None))]
fn officer_rotation_working(
    squad: &str,
    shift_start: &str,
    active: bool,
    job_title: &str,
    target_date: &str,
    base_date: &str,
    cycle_length: i32,
    rotation_schedule: Option<&Bound<'_, PyDict>>,
) -> PyResult<bool> {
    let base_ord = parse_ymd(base_date)?;
    let target_ord = parse_ymd(target_date)?;
    let mut schedule = match rotation_schedule {
        Some(dict) => rotation_schedule_from_py(dict)?,
        None => RotationSchedule::dodgeville_default(),
    };
    schedule.cycle_length = cycle_length;
    let officer = Officer {
        id: 0,
        squad: squad.to_string(),
        shift_start: shift_start.to_string(),
        active,
        job_title: job_title.to_string(),
    };
    Ok(officer_base_rotation_working(
        &officer,
        target_ord,
        base_ord,
        &schedule,
    ))
}

#[pyfunction]
#[pyo3(signature = (officers, overrides, start_date, end_date, shift_starts, base_date, cycle_length, rotation_schedule=None))]
fn compute_coverage_counts(
    py: Python<'_>,
    officers: &Bound<'_, PyList>,
    overrides: &Bound<'_, PyList>,
    start_date: &str,
    end_date: &str,
    shift_starts: Vec<String>,
    base_date: &str,
    cycle_length: i32,
    rotation_schedule: Option<&Bound<'_, PyDict>>,
) -> PyResult<PyObject> {
    let base_ord = parse_ymd(base_date)?;
    let mut schedule = match rotation_schedule {
        Some(dict) => rotation_schedule_from_py(dict)?,
        None => RotationSchedule::dodgeville_default(),
    };
    schedule.cycle_length = cycle_length;
    let officer_rows: Vec<Officer> = officers
        .iter()
        .map(|item| {
            let d: &Bound<'_, PyDict> = item.downcast().unwrap();
            Officer {
                id: d.get_item("id").unwrap().unwrap().extract().unwrap(),
                squad: d.get_item("squad").unwrap().unwrap().extract().unwrap(),
                shift_start: d.get_item("shift_start").unwrap().unwrap().extract().unwrap(),
                active: d
                    .get_item("active")
                    .unwrap()
                    .unwrap()
                    .extract()
                    .unwrap_or(true),
                job_title: optional_string(d, "job_title"),
            }
        })
        .collect();

    let mut override_rows = Vec::new();
    for item in overrides.iter() {
        let t: &Bound<'_, PyTuple> = item.downcast()?;
        let day: String = t.get_item(0)?.extract()?;
        let orig: i64 = t.get_item(1)?.extract()?;
        let repl: Option<i64> = t.get_item(2)?.extract()?;
        let covered: Option<String> = t.get_item(3)?.extract()?;
        override_rows.push((day, orig, repl, covered));
    }

    let counts = compute_shift_coverage_counts(
        &officer_rows,
        &override_rows,
        start_date,
        end_date,
        &shift_starts,
        base_ord,
        &schedule,
    )?;

    let out = PyDict::new_bound(py);
    for ((day, squad, shift), count) in counts {
        let key = PyTuple::new_bound(py, [day, squad, shift]);
        out.set_item(key, count)?;
    }
    Ok(out.into())
}

#[pyfunction]
#[pyo3(signature = (
    officer_id, assignment_date, new_shift_start, new_shift_end,
    bumped, covering, swapped, bumped_status,
    officer_shift_start, officer_shift_end, shift_times,
    base_date, cycle_length, rotation_schedule=None, covering_shifts=None
))]
fn minimum_rest_gap(
    officer_id: i64,
    assignment_date: &str,
    new_shift_start: &str,
    new_shift_end: &str,
    bumped: &Bound<'_, PyDict>,
    covering: &Bound<'_, PyDict>,
    swapped: &Bound<'_, PyDict>,
    bumped_status: &Bound<'_, PyDict>,
    officer_shift_start: &str,
    officer_shift_end: &str,
    shift_times: Vec<(String, String)>,
    base_date: &str,
    cycle_length: i32,
    rotation_schedule: Option<&Bound<'_, PyDict>>,
    covering_shifts: Option<&Bound<'_, PyDict>>,
) -> PyResult<Option<f64>> {
    let base_ord = parse_ymd(base_date)?;
    let assignment_ord = parse_ymd(assignment_date)?;
    let mut schedule = match rotation_schedule {
        Some(dict) => rotation_schedule_from_py(dict)?,
        None => RotationSchedule::dodgeville_default(),
    };
    schedule.cycle_length = cycle_length;
    let maps = py_maps_to_rust(bumped, covering, swapped, bumped_status)?;
    let covering_map = covering_shifts_from_py(covering_shifts)?;
    let officer = Officer {
        id: officer_id,
        squad: String::new(),
        shift_start: officer_shift_start.to_string(),
        active: true,
        job_title: String::new(),
    };
    Ok(minimum_rest_gap_hours_with_times(
        &officer,
        officer_shift_end,
        assignment_ord,
        new_shift_start,
        new_shift_end,
        &maps,
        base_ord,
        &schedule,
        &shift_times,
        &covering_map,
    ))
}

#[pyfunction]
#[pyo3(signature = (
    officer_id, squad, shift_start, active, job_title, end_date,
    bumped, covering, swapped, bumped_status,
    base_date, cycle_length, rotation_schedule=None, max_lookback=20
))]
fn consecutive_work_days(
    officer_id: i64,
    squad: &str,
    shift_start: &str,
    active: bool,
    job_title: &str,
    end_date: &str,
    bumped: &Bound<'_, PyDict>,
    covering: &Bound<'_, PyDict>,
    swapped: &Bound<'_, PyDict>,
    bumped_status: &Bound<'_, PyDict>,
    base_date: &str,
    cycle_length: i32,
    rotation_schedule: Option<&Bound<'_, PyDict>>,
    max_lookback: i32,
) -> PyResult<i32> {
    let base_ord = parse_ymd(base_date)?;
    let end_ord = parse_ymd(end_date)?;
    let mut schedule = match rotation_schedule {
        Some(dict) => rotation_schedule_from_py(dict)?,
        None => RotationSchedule::dodgeville_default(),
    };
    schedule.cycle_length = cycle_length;
    let maps = py_maps_to_rust(bumped, covering, swapped, bumped_status)?;
    let officer = Officer {
        id: officer_id,
        squad: squad.to_string(),
        shift_start: shift_start.to_string(),
        active,
        job_title: job_title.to_string(),
    };
    Ok(consecutive_work_days_ending(
        &officer,
        end_ord,
        base_ord,
        &schedule,
        &maps,
        max_lookback,
    ))
}

#[pyfunction]
#[pyo3(signature = (officers, overrides_on_date, original_officer_id, request_date, squad, shift_start, bump_rules, shift_times, schedule_context, night_minimum=2, min_rest_hours=8.0, max_consecutive_work_days=13, covering_shifts=None, base_date="2026-06-28", cycle_length=14, rotation_schedule=None, max_assignments_before_busy=2, max_depth=8, enforce_minimum_rest=true, enforce_consecutive_work=true))]
fn suggest_bump_chain(
    py: Python<'_>,
    officers: &Bound<'_, PyList>,
    overrides_on_date: &Bound<'_, PyList>,
    original_officer_id: i64,
    request_date: &str,
    squad: &str,
    shift_start: &str,
    bump_rules: HashMap<String, Vec<String>>,
    shift_times: Vec<(String, String)>,
    schedule_context: &Bound<'_, PyDict>,
    night_minimum: i32,
    min_rest_hours: f64,
    max_consecutive_work_days: i32,
    covering_shifts: Option<&Bound<'_, PyDict>>,
    base_date: &str,
    cycle_length: i32,
    rotation_schedule: Option<&Bound<'_, PyDict>>,
    max_assignments_before_busy: i32,
    max_depth: usize,
    enforce_minimum_rest: bool,
    enforce_consecutive_work: bool,
) -> PyResult<PyObject> {
    let base_ord = parse_ymd(base_date)?;
    let mut schedule = match rotation_schedule {
        Some(dict) => rotation_schedule_from_py(dict)?,
        None => RotationSchedule::dodgeville_default(),
    };
    schedule.cycle_length = cycle_length;
    let officer_rows: Vec<OfficerFull> = officers
        .iter()
        .map(|item| {
            let d: &Bound<'_, PyDict> = item.downcast().unwrap();
            OfficerFull {
                id: d.get_item("id").unwrap().unwrap().extract().unwrap(),
                name: d.get_item("name").unwrap().unwrap().extract().unwrap(),
                squad: d.get_item("squad").unwrap().unwrap().extract().unwrap(),
                shift_start: d.get_item("shift_start").unwrap().unwrap().extract().unwrap(),
                shift_end: d.get_item("shift_end").unwrap().unwrap().extract().unwrap(),
                active: d
                    .get_item("active")
                    .unwrap()
                    .unwrap()
                    .extract()
                    .unwrap_or(true),
                job_title: optional_string(d, "job_title"),
            }
        })
        .collect();

    let mut ov = Vec::new();
    for item in overrides_on_date.iter() {
        let t: &Bound<'_, PyTuple> = item.downcast()?;
        ov.push((
            t.get_item(0)?.extract()?,
            t.get_item(1)?.extract()?,
            t.get_item(2)?.extract()?,
            t.get_item(3)?.extract()?,
        ));
    }

    let mut day_context: HashMap<i64, (String, String)> = HashMap::new();
    for (key, value) in schedule_context.iter() {
        let officer_id: i64 = key.extract()?;
        let ctx: &Bound<'_, PyDict> = value.downcast()?;
        let status: String = ctx
            .get_item("status")?
            .unwrap()
            .extract()
            .unwrap_or_else(|_| "off".to_string());
        let assigned_start: String = ctx
            .get_item("shift_start")?
            .unwrap()
            .extract()
            .unwrap_or_default();
        day_context.insert(officer_id, (status, assigned_start));
    }

    let covering_map = covering_shifts_from_py(covering_shifts)?;

    suggest_bump_chain_py(
        py,
        officer_rows,
        &ov,
        original_officer_id,
        request_date,
        squad,
        shift_start,
        bump_rules,
        shift_times,
        day_context,
        night_minimum,
        min_rest_hours,
        max_consecutive_work_days,
        covering_map,
        base_ord,
        schedule,
        max_assignments_before_busy,
        max_depth,
        enforce_minimum_rest,
        enforce_consecutive_work,
    )
}

#[pyfunction]
fn simulate_schedule(
    py: Python<'_>,
    config: &Bound<'_, PyDict>,
    preset: &Bound<'_, PyDict>,
    sim_start_iso: &str,
) -> PyResult<PyObject> {
    simulator::simulate_schedule_py(py, config, preset, sim_start_iso)
}

#[pyfunction]
fn backend_info() -> &'static str {
    "rust/scheduler_core 0.1.0"
}

fn extract_id_set(value: &Bound<'_, PyAny>) -> PyResult<HashSet<i64>> {
    if let Ok(ids) = value.extract::<HashSet<i64>>() {
        return Ok(ids);
    }
    Ok(value.extract::<Vec<i64>>()?.into_iter().collect())
}

fn py_maps_to_rust(
    bumped: &Bound<'_, PyDict>,
    covering: &Bound<'_, PyDict>,
    swapped: &Bound<'_, PyDict>,
    bumped_status: &Bound<'_, PyDict>,
) -> PyResult<OverrideMaps> {
    let mut maps = OverrideMaps {
        bumped: HashMap::new(),
        covering: HashMap::new(),
        swapped: HashMap::new(),
        bumped_status: HashMap::new(),
    };
    for (k, v) in bumped.iter() {
        let key: String = k.extract()?;
        let ids: HashSet<i64> = extract_id_set(&v)?;
        maps.bumped.insert(key, ids);
    }
    for (k, v) in covering.iter() {
        let key: String = k.extract()?;
        let ids: HashSet<i64> = extract_id_set(&v)?;
        maps.covering.insert(key, ids);
    }
    for (k, v) in swapped.iter() {
        let key: String = k.extract()?;
        let ids: HashSet<i64> = extract_id_set(&v)?;
        maps.swapped.insert(key, ids);
    }
    for (k, v) in bumped_status.iter() {
        let key: String = k.extract()?;
        let inner: HashMap<i64, String> = v.extract()?;
        maps.bumped_status.insert(key, inner);
    }
    Ok(maps)
}

#[pymodule]
fn scheduler_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(get_cycle_day, m)?)?;
    m.add_function(wrap_pyfunction!(get_squad_on_duty, m)?)?;
    m.add_function(wrap_pyfunction!(build_schedule_matrix, m)?)?;
    m.add_function(wrap_pyfunction!(batch_day_status, m)?)?;
    m.add_function(wrap_pyfunction!(officer_rotation_working, m)?)?;
    m.add_function(wrap_pyfunction!(compute_coverage_counts, m)?)?;
    m.add_function(wrap_pyfunction!(minimum_rest_gap, m)?)?;
    m.add_function(wrap_pyfunction!(consecutive_work_days, m)?)?;
    m.add_function(wrap_pyfunction!(suggest_bump_chain, m)?)?;
    m.add_function(wrap_pyfunction!(simulate_schedule, m)?)?;
    m.add_function(wrap_pyfunction!(backend_info, m)?)?;
    Ok(())
}
