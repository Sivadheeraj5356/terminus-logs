//! Parameter recovery: golden-section search for single-parameter fits and a
//! grid search + step-halving local scan for two-parameter fits, ported
//! verbatim (including its quirks) from `reference_model.py`.

use crate::data::{InversionFit, SolverData};
use crate::error::{SolverError, SolverResult};
use crate::radiometry::{band_radiance, brightness_temperature};
use crate::thermal::{lookup_history, ThermalModel};
use serde_json::{json, Value};
use std::cell::Cell;
use std::collections::HashMap;

pub struct RadiometerRow {
    pub observation_id: String,
    pub case_id: String,
    pub time_s: f64,
    pub band_id: String,
    pub surface_temperature_k: f64,
    pub band_radiance_w_m2_sr: f64,
    pub brightness_temperature_k: f64,
}

/// Shared by both `report::build_radiometer_rows` and the inversion
/// objective so the two stay numerically identical, mirroring how the
/// Python reference reuses `build_radiometer_rows` in both places.
pub fn build_radiometer_rows_for_case(
    data: &SolverData,
    case_id: &str,
    cells_first_material_id: &str,
    history: &[(f64, Vec<f64>)],
) -> SolverResult<Vec<RadiometerRow>> {
    let mut rows = Vec::new();
    let surface_material = data.material(cells_first_material_id)?;
    for query in &data.observation_queries {
        if query.case_id != case_id {
            continue;
        }
        let temperatures = match lookup_history(history, query.time_s) {
            Some(t) => t,
            None => continue,
        };
        let surface_temperature_k = temperatures[0];
        let samples = data.band(&query.band_id)?;
        let radiance = band_radiance(
            samples,
            surface_temperature_k,
            surface_material.surface_emissivity,
            &data.config,
        );
        let brightness = brightness_temperature(samples, radiance, &data.config);
        rows.push(RadiometerRow {
            observation_id: query.observation_id.clone(),
            case_id: case_id.to_string(),
            time_s: query.time_s,
            band_id: query.band_id.clone(),
            surface_temperature_k,
            band_radiance_w_m2_sr: radiance,
            brightness_temperature_k: brightness,
        });
    }
    rows.sort_by(|a, b| a.observation_id.cmp(&b.observation_id));
    Ok(rows)
}

fn inversion_objective(
    model: &ThermalModel,
    data: &SolverData,
    fit: &InversionFit,
    parameter_values: &[f64],
) -> SolverResult<f64> {
    let mut param_map: HashMap<&str, f64> = HashMap::new();
    for (name, value) in fit.parameter_names.iter().zip(parameter_values.iter()) {
        param_map.insert(name.as_str(), *value);
    }
    let conductivity_scale = param_map.get("conductivity_scale").copied();
    let albedo_offset = param_map.get("albedo_offset").copied();

    let case_result = model.run_forward_case(&fit.case_id, conductivity_scale, albedo_offset, None)?;
    let radiometer_rows = build_radiometer_rows_for_case(
        data,
        &fit.case_id,
        &case_result.cells[0].material_id,
        &case_result.temperature_history,
    )?;
    let mut lookup: HashMap<&str, f64> = HashMap::new();
    for row in &radiometer_rows {
        lookup.insert(row.observation_id.as_str(), row.brightness_temperature_k);
    }

    let mut objective = 0.0;
    for ((obs_id, target), weight) in fit
        .observation_ids
        .iter()
        .zip(fit.target_brightness_temperatures_k.iter())
        .zip(fit.observation_weights.iter())
    {
        let predicted = *lookup
            .get(obs_id.as_str())
            .ok_or_else(|| SolverError::new(format!("Missing radiometer row for observation: {obs_id}")))?;
        let delta = predicted - target;
        objective += weight * delta * delta;
    }
    Ok(objective)
}

fn solve_one_parameter_inversion(
    model: &ThermalModel,
    data: &SolverData,
    fit: &InversionFit,
) -> SolverResult<Value> {
    let config = &data.config;
    let lower = fit.lower_bounds[0];
    let upper = fit.upper_bounds[0];
    let evaluations = Cell::new(0i64);

    let objective_at = |value: f64| -> SolverResult<f64> {
        evaluations.set(evaluations.get() + 1);
        if evaluations.get() > config.inversion_max_evaluations {
            return Err(SolverError::new(format!(
                "inversion exceeded evaluation budget for {}",
                fit.fit_id
            )));
        }
        inversion_objective(model, data, fit, &[value])
    };

    let mut left = lower;
    let mut right = upper;
    let phi = 0.5 * (5.0_f64.sqrt() - 1.0);
    let mut x1 = right - phi * (right - left);
    let mut x2 = left + phi * (right - left);
    let mut f1 = objective_at(x1)?;
    let mut f2 = objective_at(x2)?;
    let mut best_value = if f1 <= f2 { x1 } else { x2 };
    let mut best_objective = f1.min(f2);

    let tolerance = config
        .inversion_parameter_tolerance
        .max((upper - lower) * config.inversion_parameter_tolerance);

    while right - left > tolerance {
        if f1 <= f2 {
            right = x2;
            x2 = x1;
            f2 = f1;
            x1 = right - phi * (right - left);
            f1 = objective_at(x1)?;
            if f1 < best_objective {
                best_objective = f1;
                best_value = x1;
            }
        } else {
            left = x1;
            x1 = x2;
            f1 = f2;
            x2 = left + phi * (right - left);
            f2 = objective_at(x2)?;
            if f2 < best_objective {
                best_objective = f2;
                best_value = x2;
            }
        }
    }

    let at_lower = (best_value - lower).abs() <= tolerance;
    let at_upper = (best_value - upper).abs() <= tolerance;
    let converged = best_objective <= config.inversion_objective_tolerance || (right - left <= tolerance);

    Ok(json!({
        "fit_id": fit.fit_id,
        "case_id": fit.case_id,
        "parameter_names": fit.parameter_names,
        "parameter_values": [best_value],
        "objective": best_objective,
        "evaluation_count": evaluations.get(),
        "converged": converged,
        "at_parameter_bound": at_lower || at_upper,
    }))
}

fn solve_two_parameter_inversion(
    model: &ThermalModel,
    data: &SolverData,
    fit: &InversionFit,
) -> SolverResult<Value> {
    let config = &data.config;
    let evaluations = Cell::new(0i64);
    let lower_bounds = fit.lower_bounds.clone();
    let upper_bounds = fit.upper_bounds.clone();
    let mut best = fit.initial_values.clone();
    let mut best_objective = f64::INFINITY;

    let evaluate = |candidate: &[f64], best: &mut Vec<f64>, best_objective: &mut f64| -> SolverResult<f64> {
        evaluations.set(evaluations.get() + 1);
        if evaluations.get() > config.inversion_max_evaluations {
            return Err(SolverError::new(format!(
                "inversion exceeded evaluation budget for {}",
                fit.fit_id
            )));
        }
        let objective = inversion_objective(model, data, fit, candidate)?;
        if objective < *best_objective {
            *best = candidate.to_vec();
            *best_objective = objective;
        }
        Ok(objective)
    };

    let grid_size = 9usize;
    for index_a in 0..grid_size {
        let fraction_a = index_a as f64 / (grid_size - 1) as f64;
        let value_a = lower_bounds[0] + fraction_a * (upper_bounds[0] - lower_bounds[0]);
        for index_b in 0..grid_size {
            let fraction_b = index_b as f64 / (grid_size - 1) as f64;
            let value_b = lower_bounds[1] + fraction_b * (upper_bounds[1] - lower_bounds[1]);
            evaluate(&[value_a, value_b], &mut best, &mut best_objective)?;
        }
    }

    let phi = 0.5 * ((5.0_f64).sqrt() - 1.0);
    for _pass in 0..4 {
        for index in 0..2usize {
            let mut left = lower_bounds[index];
            let mut right = upper_bounds[index];
            let mut x1 = right - phi * (right - left);
            let mut x2 = left + phi * (right - left);
            let mut candidate = best.clone();
            candidate[index] = x1;
            let mut f1 = evaluate(&candidate, &mut best, &mut best_objective)?;
            candidate = best.clone();
            candidate[index] = x2;
            let mut f2 = evaluate(&candidate, &mut best, &mut best_objective)?;
            let tolerance = config
                .inversion_parameter_tolerance
                .max((upper_bounds[index] - lower_bounds[index]) * config.inversion_parameter_tolerance);
            while right - left > tolerance && evaluations.get() < config.inversion_max_evaluations {
                if f1 <= f2 {
                    right = x2;
                    x2 = x1;
                    f2 = f1;
                    x1 = right - phi * (right - left);
                    candidate = best.clone();
                    candidate[index] = x1;
                    f1 = evaluate(&candidate, &mut best, &mut best_objective)?;
                } else {
                    left = x1;
                    x1 = x2;
                    f1 = f2;
                    x2 = left + phi * (right - left);
                    candidate = best.clone();
                    candidate[index] = x2;
                    f2 = evaluate(&candidate, &mut best, &mut best_objective)?;
                }
            }
        }
    }

    let at_bound = (0..2).any(|index| {
        (best[index] - lower_bounds[index]).abs() <= config.inversion_parameter_tolerance
            || (best[index] - upper_bounds[index]).abs() <= config.inversion_parameter_tolerance
    });
    let converged = best_objective <= config.inversion_objective_tolerance;

    Ok(json!({
        "fit_id": fit.fit_id,
        "case_id": fit.case_id,
        "parameter_names": fit.parameter_names,
        "parameter_values": best,
        "objective": best_objective,
        "evaluation_count": evaluations.get(),
        "converged": converged,
        "at_parameter_bound": at_bound,
    }))
}

pub fn solve_inversion_fit(model: &ThermalModel, data: &SolverData, fit: &InversionFit) -> SolverResult<Value> {
    match fit.parameter_names.len() {
        1 => solve_one_parameter_inversion(model, data, fit),
        2 => solve_two_parameter_inversion(model, data, fit),
        _ => Err(SolverError::new(format!(
            "unsupported inversion parameter count for {}",
            fit.fit_id
        ))),
    }
}
