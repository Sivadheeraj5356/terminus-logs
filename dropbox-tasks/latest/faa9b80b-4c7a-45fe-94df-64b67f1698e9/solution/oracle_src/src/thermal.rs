//! Nonuniform finite-volume heat conduction with temperature-dependent
//! properties, nonlinear surface radiation, spin-up and period simulation.

use crate::data::{EclipsePoint, ForcingInterval, GridCell, IlluminationCase, Material, SolverData};
use crate::error::SolverResult;
use serde_json::{json, Value};
use std::collections::HashMap;

pub fn clamp(value: f64, lower: f64, upper: f64) -> f64 {
    value.max(lower).min(upper)
}

/// Mirrors Python's `dict` exact-key lookup on `temperature_history[time_s]`:
/// history keys are produced by identical `start_time_s + step_index * dt`
/// arithmetic in both implementations, so bit-exact equality is the correct
/// (and intentionally non-fuzzy) matching rule here.
pub fn lookup_history<'a>(history: &'a [(f64, Vec<f64>)], time_s: f64) -> Option<&'a Vec<f64>> {
    history
        .iter()
        .find(|(t, _)| *t == time_s)
        .map(|(_, temps)| temps)
}

pub fn effective_albedo(material: &Material, albedo_offset: f64) -> f64 {
    clamp(material.surface_albedo + albedo_offset, 0.0, 1.0)
}

/// Surface radiative loss in the heat equation is enabled only when the case
/// requests a loose spin-up tolerance (>= 1 K). Micro radiometry fixtures use
/// Surface radiation always uses the declared material emissivity. Zero is the
/// only public way to disable the thermal \(\varepsilon\sigma T^4\) term.
pub fn thermal_surface_emissivity(material: &Material, _case: &IlluminationCase) -> f64 {
    material.surface_emissivity
}

pub fn cell_energy(material: &Material, thickness_m: f64, temperature_k: f64) -> f64 {
    let rho = material.density_kg_m3;
    let c0 = material.heat_capacity_c0_j_kg_k;
    let c1 = material.heat_capacity_c1_j_kg_k2;
    let c2 = material.heat_capacity_c2_j_kg_k3;
    let t = temperature_k;
    rho * thickness_m * (c0 * t + 0.5 * c1 * t * t + (1.0 / 3.0) * c2 * t * t * t)
}

pub fn cell_conductivity(
    material: &Material,
    temperature_k: f64,
    center_depth_m: f64,
    conductivity_scale: f64,
) -> f64 {
    conductivity_scale
        * material.contact_conductivity_w_m_k
        * (1.0 + material.conductivity_depth_gradient_per_m * center_depth_m)
        + material.radiative_conductivity_w_m_k4 * temperature_k.powi(3)
}

pub fn interpolate_linear(times: &[f64], values: &[f64], query_time_s: f64) -> f64 {
    let n = times.len();
    if query_time_s <= times[0] {
        return values[0];
    }
    if query_time_s >= times[n - 1] {
        return values[n - 1];
    }
    for index in 0..n - 1 {
        let t0 = times[index];
        let t1 = times[index + 1];
        if t0 <= query_time_s && query_time_s <= t1 {
            if t1 == t0 {
                return values[index + 1];
            }
            let fraction = (query_time_s - t0) / (t1 - t0);
            return values[index] + fraction * (values[index + 1] - values[index]);
        }
    }
    values[n - 1]
}

pub fn cos_incidence_at_time(intervals: &[ForcingInterval], time_s: f64) -> f64 {
    for interval in intervals {
        if interval.start_time_s <= time_s && time_s <= interval.end_time_s {
            let span = interval.end_time_s - interval.start_time_s;
            let cos_value = if span <= 0.0 {
                interval.cos_incidence_start
            } else {
                let fraction = (time_s - interval.start_time_s) / span;
                interval.cos_incidence_start
                    + fraction * (interval.cos_incidence_end - interval.cos_incidence_start)
            };
            return cos_value.max(0.0);
        }
    }
    let last = intervals.last().expect("forcing intervals must not be empty");
    last.cos_incidence_end.max(0.0)
}

pub fn eclipse_transmission_at_time(
    profiles: &HashMap<String, Vec<EclipsePoint>>,
    profile_id: &str,
    time_s: f64,
) -> f64 {
    if profile_id == "none" {
        return 1.0;
    }
    let points = profiles
        .get(profile_id)
        .unwrap_or_else(|| panic!("Missing eclipse profile: {profile_id}"));
    let times: Vec<f64> = points.iter().map(|p| p.profile_time_s).collect();
    let values: Vec<f64> = points.iter().map(|p| p.transmission_fraction).collect();
    interpolate_linear(&times, &values, time_s)
}

pub fn absorbed_solar_flux(
    case: &IlluminationCase,
    material: &Material,
    intervals: &[ForcingInterval],
    profiles: &HashMap<String, Vec<EclipsePoint>>,
    time_s: f64,
    albedo_offset: f64,
) -> f64 {
    let albedo = effective_albedo(material, albedo_offset);
    let cos_value = cos_incidence_at_time(intervals, time_s);
    for interval in intervals {
        if interval.start_time_s <= time_s && time_s <= interval.end_time_s {
            let transmission =
                eclipse_transmission_at_time(profiles, &interval.eclipse_profile_id, time_s);
            return (1.0 - albedo) * case.solar_flux_w_m2 * cos_value * transmission;
        }
    }
    let interval = intervals.last().expect("forcing intervals must not be empty");
    let transmission = eclipse_transmission_at_time(profiles, &interval.eclipse_profile_id, time_s);
    (1.0 - albedo) * case.solar_flux_w_m2 * cos_value * transmission
}

#[derive(Debug, Clone, Default)]
pub struct Fluxes {
    pub absorbed_solar_flux_w_m2: f64,
    pub emitted_thermal_flux_w_m2: f64,
    pub conductive_flux_down_w_m2: f64,
    pub geothermal_flux_up_w_m2: f64,
    pub q_surface_down: f64,
    pub q_bottom_down: f64,
}

struct ResidualResult {
    residuals: Vec<f64>,
    q_solar: f64,
    q_emit: f64,
    conductive_surface: f64,
    q_surface_down: f64,
    q_bottom_down: f64,
}

pub struct PeriodResult {
    pub final_temperatures: Vec<f64>,
    pub cycle_difference_k: f64,
    pub time_step_rows: Vec<Value>,
    pub surface_flux_rows: Vec<Value>,
    pub temperature_history: Vec<(f64, Vec<f64>)>,
}

#[derive(Clone)]
pub struct ForwardCaseResult {
    pub case_id: String,
    pub cells: Vec<GridCell>,
    pub spinup_cycles: i64,
    pub final_spinup_difference_k: f64,
    pub time_step_rows: Vec<Value>,
    pub surface_flux_rows: Vec<Value>,
    pub temperature_history: Vec<(f64, Vec<f64>)>,
    pub conductivity_scale: f64,
    pub albedo_offset: f64,
}

/// Gaussian elimination with partial pivoting, mirroring `numpy.linalg.solve`
/// for the small dense Jacobians produced by the finite-difference Newton step.
fn solve_linear_system(matrix: &[Vec<f64>], rhs: &[f64]) -> Option<Vec<f64>> {
    let n = rhs.len();
    let mut aug: Vec<Vec<f64>> = matrix.to_vec();
    let mut b = rhs.to_vec();

    for col in 0..n {
        let mut pivot_row = col;
        let mut pivot_val = aug[col][col].abs();
        for row in (col + 1)..n {
            let value = aug[row][col].abs();
            if value > pivot_val {
                pivot_val = value;
                pivot_row = row;
            }
        }
        if pivot_val < 1e-300 {
            return None;
        }
        if pivot_row != col {
            aug.swap(pivot_row, col);
            b.swap(pivot_row, col);
        }

        let pivot = aug[col][col];
        for j in col..n {
            aug[col][j] /= pivot;
        }
        b[col] /= pivot;

        for row in 0..n {
            if row == col {
                continue;
            }
            let factor = aug[row][col];
            if factor == 0.0 {
                continue;
            }
            for j in col..n {
                aug[row][j] -= factor * aug[col][j];
            }
            b[row] -= factor * b[col];
        }
    }
    Some(b)
}

pub struct ThermalModel<'a> {
    pub data: &'a SolverData,
}

impl<'a> ThermalModel<'a> {
    pub fn new(data: &'a SolverData) -> Self {
        ThermalModel { data }
    }

    fn clip_temperatures(&self, temperatures: &[f64]) -> Vec<f64> {
        let config = &self.data.config;
        temperatures
            .iter()
            .map(|&t| clamp(t, config.minimum_temperature_k, config.maximum_temperature_k))
            .collect()
    }

    fn harmonic_flux(
        &self,
        cells: &[GridCell],
        temperatures: &[f64],
        conductivity_scale: f64,
        face_index: usize,
    ) -> f64 {
        let left_index = face_index;
        let right_index = face_index + 1;
        let left_cell = &cells[left_index];
        let right_cell = &cells[right_index];
        let left_material = self
            .data
            .materials
            .get(&left_cell.material_id)
            .unwrap_or_else(|| panic!("Missing material id: {}", left_cell.material_id));
        let right_material = self
            .data
            .materials
            .get(&right_cell.material_id)
            .unwrap_or_else(|| panic!("Missing material id: {}", right_cell.material_id));
        let k_left = cell_conductivity(
            left_material,
            temperatures[left_index],
            left_cell.center_depth_m(),
            conductivity_scale,
        );
        let k_right = cell_conductivity(
            right_material,
            temperatures[right_index],
            right_cell.center_depth_m(),
            conductivity_scale,
        );
        let z_face = left_cell.bottom_depth_m;
        let z_left = left_cell.center_depth_m();
        let z_right = right_cell.center_depth_m();
        let denominator = (z_face - z_left) / k_left + (z_right - z_face) / k_right;
        if denominator <= 0.0 {
            return 0.0;
        }
        (temperatures[left_index] - temperatures[right_index]) / denominator
    }

    fn surface_flux_down(
        &self,
        case: &IlluminationCase,
        material: &Material,
        intervals: &[ForcingInterval],
        time_s: f64,
        surface_temperature_k: f64,
        albedo_offset: f64,
    ) -> (f64, f64, f64) {
        let q_solar = absorbed_solar_flux(
            case,
            material,
            intervals,
            &self.data.eclipse_profiles,
            time_s,
            albedo_offset,
        );
        let emissivity = thermal_surface_emissivity(material, case);
        let q_emit = emissivity
            * self.data.config.stefan_boltzmann_w_m2_k4
            * surface_temperature_k.powi(4);
        (q_solar - q_emit, q_solar, q_emit)
    }

    fn residuals(
        &self,
        cells: &[GridCell],
        case: &IlluminationCase,
        intervals: &[ForcingInterval],
        temperatures_new: &[f64],
        temperatures_old: &[f64],
        time_s: f64,
        conductivity_scale: f64,
        albedo_offset: f64,
    ) -> ResidualResult {
        let dt = self.data.config.time_step_s;
        let count = cells.len();
        let mut residuals = vec![0.0; count];
        let surface_material = self
            .data
            .materials
            .get(&cells[0].material_id)
            .unwrap_or_else(|| panic!("Missing material id: {}", cells[0].material_id));
        let (q_surface_down, q_solar, q_emit) = self.surface_flux_down(
            case,
            surface_material,
            intervals,
            time_s,
            temperatures_new[0],
            albedo_offset,
        );
        let q_bottom_down = -case.geothermal_flux_w_m2;

        for index in 0..count {
            let material = self
                .data
                .materials
                .get(&cells[index].material_id)
                .unwrap_or_else(|| panic!("Missing material id: {}", cells[index].material_id));
            let energy_old = cell_energy(material, cells[index].thickness_m(), temperatures_old[index]);
            let energy_new = cell_energy(material, cells[index].thickness_m(), temperatures_new[index]);
            let q_top = if index == 0 {
                q_surface_down
            } else {
                self.harmonic_flux(cells, temperatures_new, conductivity_scale, index - 1)
            };
            let q_bottom = if index == count - 1 {
                q_bottom_down
            } else {
                self.harmonic_flux(cells, temperatures_new, conductivity_scale, index)
            };
            residuals[index] = (energy_new - energy_old) / dt - (q_top - q_bottom);
        }

        let conductive_surface = if count > 1 {
            self.harmonic_flux(cells, temperatures_new, conductivity_scale, 0)
        } else {
            0.0
        };

        ResidualResult {
            residuals,
            q_solar,
            q_emit,
            conductive_surface,
            q_surface_down,
            q_bottom_down,
        }
    }

    #[allow(clippy::too_many_arguments)]
    pub fn solve_nonlinear_step(
        &self,
        cells: &[GridCell],
        case: &IlluminationCase,
        intervals: &[ForcingInterval],
        temperatures_old: &[f64],
        time_s: f64,
        conductivity_scale: f64,
        albedo_offset: f64,
    ) -> (Vec<f64>, i64, f64, Fluxes) {
        let config = &self.data.config;
        let n = cells.len();
        let mut temperatures = self.clip_temperatures(temperatures_old);
        let max_iterations = config.nonlinear_max_iterations;
        let mut max_residual = f64::INFINITY;
        let mut iterations: i64 = 0;
        let mut fluxes = Fluxes::default();

        for iteration in 0..max_iterations {
            let res = self.residuals(
                cells,
                case,
                intervals,
                &temperatures,
                temperatures_old,
                time_s,
                conductivity_scale,
                albedo_offset,
            );
            max_residual = res
                .residuals
                .iter()
                .fold(0.0_f64, |acc, &value| acc.max(value.abs()));
            fluxes = Fluxes {
                absorbed_solar_flux_w_m2: res.q_solar,
                emitted_thermal_flux_w_m2: res.q_emit,
                conductive_flux_down_w_m2: res.conductive_surface,
                geothermal_flux_up_w_m2: case.geothermal_flux_w_m2,
                q_surface_down: res.q_surface_down,
                q_bottom_down: res.q_bottom_down,
            };
            if max_residual <= config.nonlinear_residual_tolerance_w_m2 {
                iterations = iteration + 1;
                break;
            }

            let delta_temperature = config.nonlinear_temperature_tolerance_k.max(1.0e-6);
            let mut jacobian = vec![vec![0.0; n]; n];
            for column in 0..n {
                let mut perturbed = temperatures.clone();
                let step = delta_temperature * perturbed[column].abs().max(1.0);
                perturbed[column] += step;
                let perturbed = self.clip_temperatures(&perturbed);
                let perturbed_res = self.residuals(
                    cells,
                    case,
                    intervals,
                    &perturbed,
                    temperatures_old,
                    time_s,
                    conductivity_scale,
                    albedo_offset,
                );
                let denom = perturbed[column] - temperatures[column];
                for row in 0..n {
                    jacobian[row][column] = (perturbed_res.residuals[row] - res.residuals[row]) / denom;
                }
            }

            let neg_residuals: Vec<f64> = res.residuals.iter().map(|v| -v).collect();
            let delta = match solve_linear_system(&jacobian, &neg_residuals) {
                Some(d) => d,
                None => res.residuals.iter().map(|v| -0.1 * v).collect(),
            };

            let mut alpha = 1.0_f64;
            let mut accepted = false;
            let mut new_temperatures = temperatures.clone();
            while alpha >= config.line_search_min_factor {
                let trial: Vec<f64> = temperatures
                    .iter()
                    .zip(delta.iter())
                    .map(|(&t, &d)| t + alpha * d)
                    .collect();
                let trial = self.clip_temperatures(&trial);
                let trial_res = self.residuals(
                    cells,
                    case,
                    intervals,
                    &trial,
                    temperatures_old,
                    time_s,
                    conductivity_scale,
                    albedo_offset,
                );
                let trial_max = trial_res
                    .residuals
                    .iter()
                    .fold(0.0_f64, |acc, &value| acc.max(value.abs()));
                if trial_max < max_residual {
                    new_temperatures = trial;
                    accepted = true;
                    break;
                }
                alpha *= 0.5;
            }
            if accepted {
                temperatures = new_temperatures;
            } else {
                let adjusted: Vec<f64> = temperatures
                    .iter()
                    .zip(res.residuals.iter())
                    .map(|(&t, &r)| t - 0.05 * r)
                    .collect();
                temperatures = self.clip_temperatures(&adjusted);
            }
            iterations = iteration + 1;
        }

        (temperatures, iterations, max_residual, fluxes)
    }

    #[allow(clippy::too_many_arguments)]
    pub fn simulate_period(
        &self,
        cells: &[GridCell],
        case: &IlluminationCase,
        intervals: &[ForcingInterval],
        initial_temperatures: &[f64],
        conductivity_scale: f64,
        albedo_offset: f64,
        record: bool,
        start_time_s: f64,
    ) -> PeriodResult {
        let dt = self.data.config.time_step_s;
        let steps = (case.period_s / dt).round() as i64;
        let mut temperatures = self.clip_temperatures(initial_temperatures);
        let start_profile = temperatures.clone();
        let mut time_step_rows = Vec::new();
        let mut surface_flux_rows = Vec::new();
        let mut temperature_history: Vec<(f64, Vec<f64>)> = Vec::new();

        for step_index in 0..steps {
            let start_time = start_time_s + (step_index as f64) * dt;
            let end_time = start_time + dt;
            let old_temperatures = temperatures.clone();
            let (new_temperatures, nonlinear_iterations, max_residual, fluxes) = self
                .solve_nonlinear_step(
                    cells,
                    case,
                    intervals,
                    &old_temperatures,
                    end_time,
                    conductivity_scale,
                    albedo_offset,
                );
            temperatures = new_temperatures;

            if record {
                temperature_history.push((end_time, temperatures.clone()));
                let mut stored_change = 0.0;
                for (cell_index, cell) in cells.iter().enumerate() {
                    let material = self
                        .data
                        .materials
                        .get(&cell.material_id)
                        .unwrap_or_else(|| panic!("Missing material id: {}", cell.material_id));
                    stored_change += cell_energy(material, cell.thickness_m(), temperatures[cell_index])
                        - cell_energy(material, cell.thickness_m(), old_temperatures[cell_index]);
                }
                let net_boundary = dt * (fluxes.q_surface_down - fluxes.q_bottom_down);
                let energy_residual = stored_change - net_boundary;
                let converged = max_residual <= self.data.config.nonlinear_residual_tolerance_w_m2;

                time_step_rows.push(json!({
                    "case_id": case.case_id,
                    "step_index": step_index,
                    "start_time_s": start_time,
                    "end_time_s": end_time,
                    "nonlinear_iterations": nonlinear_iterations,
                    "maximum_residual_w_m2": max_residual,
                    "converged": converged,
                }));
                surface_flux_rows.push(json!({
                    "case_id": case.case_id,
                    "step_index": step_index,
                    "end_time_s": end_time,
                    "absorbed_solar_flux_w_m2": fluxes.absorbed_solar_flux_w_m2,
                    "emitted_thermal_flux_w_m2": fluxes.emitted_thermal_flux_w_m2,
                    "conductive_flux_down_w_m2": fluxes.conductive_flux_down_w_m2,
                    "geothermal_flux_up_w_m2": fluxes.geothermal_flux_up_w_m2,
                    "stored_energy_change_j_m2": stored_change,
                    "net_boundary_energy_j_m2": net_boundary,
                    "energy_residual_j_m2": energy_residual,
                }));
            }
        }

        let cycle_difference = temperatures
            .iter()
            .zip(start_profile.iter())
            .fold(0.0_f64, |acc, (&a, &b)| acc.max((a - b).abs()));

        PeriodResult {
            final_temperatures: temperatures,
            cycle_difference_k: cycle_difference,
            time_step_rows,
            surface_flux_rows,
            temperature_history,
        }
    }

    pub fn run_forward_case(
        &self,
        case_id: &str,
        conductivity_scale: Option<f64>,
        albedo_offset: Option<f64>,
        maximum_spinup_cycles: Option<i64>,
    ) -> SolverResult<ForwardCaseResult> {
        let case = self
            .data
            .illumination_cases
            .get(case_id)
            .ok_or_else(|| crate::error::SolverError::new(format!("Missing illumination case: {case_id}")))?;
        let cells = self.data.cells_for_case(case_id)?.clone();
        let intervals = self.data.intervals_for_case(case_id)?;
        let scale = conductivity_scale.unwrap_or(case.conductivity_scale);
        let offset = albedo_offset.unwrap_or(case.albedo_offset);
        let max_cycles = maximum_spinup_cycles.unwrap_or(case.maximum_spinup_cycles);

        // Public spin-up contract: start from the grid initial profile only.
        // No hidden steady-state warm-start (that path was singular for ε=0).
        let initial: Vec<f64> = cells.iter().map(|cell| cell.initial_temperature_k).collect();
        let mut temperatures = self.clip_temperatures(&initial);
        let mut spinup_cycles: i64 = 0;
        let mut final_spinup_difference = f64::INFINITY;
        let mut converged_spinup = false;

        while spinup_cycles < max_cycles {
            spinup_cycles += 1;
            let period_result =
                self.simulate_period(&cells, case, intervals, &temperatures, scale, offset, false, 0.0);
            temperatures = period_result.final_temperatures;
            final_spinup_difference = period_result.cycle_difference_k;
            if final_spinup_difference <= case.spinup_tolerance_k {
                converged_spinup = true;
                break;
            }
        }
        if !converged_spinup {
            return Err(crate::error::SolverError::new(format!(
                "spin-up failed for {case_id} after {max_cycles} cycles"
            )));
        }

        let report_result =
            self.simulate_period(&cells, case, intervals, &temperatures, scale, offset, true, 0.0);

        Ok(ForwardCaseResult {
            case_id: case_id.to_string(),
            cells,
            spinup_cycles,
            final_spinup_difference_k: final_spinup_difference,
            time_step_rows: report_result.time_step_rows,
            surface_flux_rows: report_result.surface_flux_rows,
            temperature_history: report_result.temperature_history,
            conductivity_scale: scale,
            albedo_offset: offset,
        })
    }
}
