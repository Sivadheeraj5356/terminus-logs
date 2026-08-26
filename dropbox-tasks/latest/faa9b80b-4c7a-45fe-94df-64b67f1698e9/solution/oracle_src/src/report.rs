//! Assembly of the final report: per-case forward simulation, temperature
//! and radiometer tables, inversion fits, summary statistics and rounding.

use crate::data::SolverData;
use crate::error::SolverResult;
use crate::inversion::{build_radiometer_rows_for_case, solve_inversion_fit};
use crate::thermal::{lookup_history, ThermalModel};
use serde_json::{json, Map, Number, Value};
use std::cmp::Ordering;

fn canonical_observation_count(data: &SolverData) -> i64 {
    data.observation_queries.len() as i64
}

fn build_temperature_rows(
    data: &SolverData,
    case_id: &str,
    cells: &[crate::data::GridCell],
    history: &[(f64, Vec<f64>)],
) -> Vec<Value> {
    let mut rows = Vec::new();
    for query in &data.observation_queries {
        if query.case_id != case_id {
            continue;
        }
        let temperatures = match lookup_history(history, query.time_s) {
            Some(t) => t,
            None => continue,
        };
        for cell in cells {
            let index = cell.cell_index as usize;
            rows.push(json!({
                "case_id": case_id,
                "observation_id": query.observation_id,
                "time_s": query.time_s,
                "cell_index": cell.cell_index,
                "depth_center_m": cell.center_depth_m(),
                "temperature_k": temperatures[index],
            }));
        }
    }
    rows.sort_by(|a, b| compare_rows(a, b, &["case_id", "observation_id", "cell_index"]));
    rows
}

fn build_radiometer_rows(
    data: &SolverData,
    case_id: &str,
    first_material_id: &str,
    history: &[(f64, Vec<f64>)],
) -> SolverResult<Vec<Value>> {
    let rows = build_radiometer_rows_for_case(data, case_id, first_material_id, history)?;
    Ok(rows
        .into_iter()
        .map(|row| {
            json!({
                "observation_id": row.observation_id,
                "case_id": row.case_id,
                "time_s": row.time_s,
                "band_id": row.band_id,
                "surface_temperature_k": row.surface_temperature_k,
                "band_radiance_w_m2_sr": row.band_radiance_w_m2_sr,
                "brightness_temperature_k": row.brightness_temperature_k,
            })
        })
        .collect())
}

fn value_as_f64(value: &Value, key: &str) -> f64 {
    value
        .get(key)
        .and_then(Value::as_f64)
        .unwrap_or_else(|| panic!("Missing numeric field: {key}"))
}

fn compare_rows(a: &Value, b: &Value, keys: &[&str]) -> Ordering {
    for key in keys {
        let ordering = if let (Some(sa), Some(sb)) = (a.get(*key).and_then(Value::as_str), b.get(*key).and_then(Value::as_str)) {
            sa.cmp(sb)
        } else {
            let fa = value_as_f64(a, key);
            let fb = value_as_f64(b, key);
            fa.partial_cmp(&fb).unwrap_or(Ordering::Equal)
        };
        if ordering != Ordering::Equal {
            return ordering;
        }
    }
    Ordering::Equal
}

fn min_or_default(values: &[f64], default: f64) -> f64 {
    if values.is_empty() {
        default
    } else {
        values.iter().cloned().fold(f64::INFINITY, f64::min)
    }
}

fn max_or_default(values: &[f64], default: f64) -> f64 {
    if values.is_empty() {
        default
    } else {
        values.iter().cloned().fold(f64::NEG_INFINITY, f64::max)
    }
}

pub fn build_report(data: &SolverData) -> SolverResult<Value> {
    let model = ThermalModel::new(data);
    let decimal_places = data.config.output_decimal_places;

    let mut time_step_rows: Vec<Value> = Vec::new();
    let mut temperature_rows: Vec<Value> = Vec::new();
    let mut surface_flux_rows: Vec<Value> = Vec::new();
    let mut radiometer_rows: Vec<Value> = Vec::new();
    let mut solver_diagnostics: Vec<Value> = Vec::new();

    let mut case_ids: Vec<&String> = data.illumination_cases.keys().collect();
    case_ids.sort();

    for case_id in &case_ids {
        let case_result = model.run_forward_case(case_id, None, None, None)?;

        time_step_rows.extend(case_result.time_step_rows.iter().cloned());
        surface_flux_rows.extend(case_result.surface_flux_rows.iter().cloned());
        temperature_rows.extend(build_temperature_rows(
            data,
            case_id,
            &case_result.cells,
            &case_result.temperature_history,
        ));
        radiometer_rows.extend(build_radiometer_rows(
            data,
            case_id,
            &case_result.cells[0].material_id,
            &case_result.temperature_history,
        )?);

        let max_step_residual = case_result
            .time_step_rows
            .iter()
            .map(|row| value_as_f64(row, "maximum_residual_w_m2"))
            .fold(f64::NEG_INFINITY, f64::max);

        let all_temperatures: Vec<f64> = case_result
            .temperature_history
            .iter()
            .flat_map(|(_, temps)| temps.iter().cloned())
            .collect();
        let minimum_temperature_k = all_temperatures.iter().cloned().fold(f64::INFINITY, f64::min);
        let maximum_temperature_k = all_temperatures.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        let all_values_finite = all_temperatures.iter().all(|v| v.is_finite());

        solver_diagnostics.push(json!({
            "case_id": case_id,
            "spinup_cycles": case_result.spinup_cycles,
            "final_spinup_difference_k": case_result.final_spinup_difference_k,
            "report_step_count": case_result.time_step_rows.len() as i64,
            "maximum_step_residual_w_m2": max_step_residual,
            "minimum_temperature_k": minimum_temperature_k,
            "maximum_temperature_k": maximum_temperature_k,
            "all_values_finite": all_values_finite,
        }));
    }

    time_step_rows.sort_by(|a, b| compare_rows(a, b, &["case_id", "step_index"]));
    surface_flux_rows.sort_by(|a, b| compare_rows(a, b, &["case_id", "step_index"]));
    temperature_rows.sort_by(|a, b| compare_rows(a, b, &["case_id", "observation_id", "cell_index"]));
    radiometer_rows.sort_by(|a, b| compare_rows(a, b, &["observation_id"]));
    solver_diagnostics.sort_by(|a, b| compare_rows(a, b, &["case_id"]));

    let mut fits: Vec<&crate::data::InversionFit> = data.inversion_fits.iter().collect();
    fits.sort_by(|a, b| a.fit_id.cmp(&b.fit_id));
    let mut inverse_fit_rows: Vec<Value> = Vec::new();
    for fit in fits {
        inverse_fit_rows.push(solve_inversion_fit(&model, data, fit)?);
    }
    inverse_fit_rows.sort_by(|a, b| compare_rows(a, b, &["fit_id"]));

    let converged_inverse_fit_count = inverse_fit_rows
        .iter()
        .filter(|row| row.get("converged").and_then(Value::as_bool).unwrap_or(false))
        .count() as i64;

    let surface_temperature_values: Vec<f64> = radiometer_rows
        .iter()
        .map(|row| value_as_f64(row, "surface_temperature_k"))
        .collect();
    let brightness_values: Vec<f64> = radiometer_rows
        .iter()
        .map(|row| value_as_f64(row, "brightness_temperature_k"))
        .collect();
    let energy_residuals: Vec<f64> = surface_flux_rows
        .iter()
        .map(|row| value_as_f64(row, "energy_residual_j_m2").abs())
        .collect();
    let objectives: Vec<f64> = inverse_fit_rows
        .iter()
        .map(|row| value_as_f64(row, "objective"))
        .collect();

    let summary = json!({
        "case_count": case_ids.len() as i64,
        "observation_count": canonical_observation_count(data),
        "radiometer_row_count": radiometer_rows.len() as i64,
        "inverse_fit_count": inverse_fit_rows.len() as i64,
        "converged_inverse_fit_count": converged_inverse_fit_count,
        "minimum_surface_temperature_k": min_or_default(&surface_temperature_values, 0.0),
        "maximum_surface_temperature_k": max_or_default(&surface_temperature_values, 0.0),
        "maximum_brightness_temperature_k": max_or_default(&brightness_values, 0.0),
        "minimum_inversion_objective": min_or_default(&objectives, 0.0),
        "maximum_absolute_energy_residual_j_m2": max_or_default(&energy_residuals, 0.0),
    });

    let report = json!({
        "time_step_rows": time_step_rows,
        "temperature_rows": temperature_rows,
        "surface_flux_rows": surface_flux_rows,
        "radiometer_rows": radiometer_rows,
        "inverse_fit_rows": inverse_fit_rows,
        "solver_diagnostics": solver_diagnostics,
        "summary": summary,
    });

    Ok(round_output_value(&report, decimal_places))
}

/// Ports Python's `round(value, decimal_places)` (correctly-rounded,
/// ties-to-even) via string formatting rather than a multiply/divide, to
/// avoid compounding floating-point error on repeated rounding.
fn round_half_even(value: f64, decimal_places: i32) -> f64 {
    if !value.is_finite() || decimal_places < 0 {
        return value;
    }
    let formatted = format!("{:.*}", decimal_places as usize, value);
    formatted.parse::<f64>().unwrap_or(value)
}

pub fn round_output_value(value: &Value, decimal_places: i32) -> Value {
    match value {
        Value::Bool(b) => Value::Bool(*b),
        Value::Number(n) => {
            if n.is_i64() || n.is_u64() {
                Value::Number(n.clone())
            } else if let Some(f) = n.as_f64() {
                match Number::from_f64(round_half_even(f, decimal_places)) {
                    Some(rounded) => Value::Number(rounded),
                    None => Value::Number(n.clone()),
                }
            } else {
                Value::Number(n.clone())
            }
        }
        Value::Array(items) => Value::Array(items.iter().map(|v| round_output_value(v, decimal_places)).collect()),
        Value::Object(map) => {
            let mut result = Map::new();
            for (key, item) in map.iter() {
                result.insert(key.clone(), round_output_value(item, decimal_places));
            }
            Value::Object(result)
        }
        other => other.clone(),
    }
}

pub fn contains_non_finite(value: &Value) -> bool {
    match value {
        Value::Number(n) => n.as_f64().map(|f| !f.is_finite()).unwrap_or(false),
        Value::Array(items) => items.iter().any(contains_non_finite),
        Value::Object(map) => map.values().any(contains_non_finite),
        _ => false,
    }
}
