//! Public report and intermediate model types.
//!
//! Field names match `/app/docs/report_contract.md`. Numerical solvers live in
//! other modules that candidates must implement.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeStepRow {
    pub case_id: String,
    pub step_index: i64,
    pub start_time_s: f64,
    pub end_time_s: f64,
    pub nonlinear_iterations: i64,
    pub maximum_residual_w_m2: f64,
    pub converged: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemperatureRow {
    pub case_id: String,
    pub observation_id: String,
    pub time_s: f64,
    pub cell_index: i64,
    pub depth_center_m: f64,
    pub temperature_k: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SurfaceFluxRow {
    pub case_id: String,
    pub step_index: i64,
    pub end_time_s: f64,
    pub absorbed_solar_flux_w_m2: f64,
    pub emitted_thermal_flux_w_m2: f64,
    pub conductive_flux_down_w_m2: f64,
    pub geothermal_flux_up_w_m2: f64,
    pub stored_energy_change_j_m2: f64,
    pub net_boundary_energy_j_m2: f64,
    pub energy_residual_j_m2: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RadiometerRow {
    pub observation_id: String,
    pub case_id: String,
    pub time_s: f64,
    pub band_id: String,
    pub surface_temperature_k: f64,
    pub band_radiance_w_m2_sr: f64,
    pub brightness_temperature_k: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InverseFitRow {
    pub fit_id: String,
    pub case_id: String,
    pub parameter_names: Vec<String>,
    pub parameter_values: Vec<f64>,
    pub objective: f64,
    pub evaluation_count: i64,
    pub converged: bool,
    pub at_parameter_bound: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SolverDiagnostics {
    pub case_id: String,
    pub spinup_cycles: i64,
    pub final_spinup_difference_k: f64,
    pub report_step_count: i64,
    pub maximum_step_residual_w_m2: f64,
    pub minimum_temperature_k: f64,
    pub maximum_temperature_k: f64,
    pub all_values_finite: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReportSummary {
    pub case_count: i64,
    pub observation_count: i64,
    pub radiometer_row_count: i64,
    pub inverse_fit_count: i64,
    pub converged_inverse_fit_count: i64,
    pub minimum_surface_temperature_k: f64,
    pub maximum_surface_temperature_k: f64,
    pub maximum_brightness_temperature_k: f64,
    pub minimum_inversion_objective: f64,
    pub maximum_absolute_energy_residual_j_m2: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SolverReport {
    pub time_step_rows: Vec<TimeStepRow>,
    pub temperature_rows: Vec<TemperatureRow>,
    pub surface_flux_rows: Vec<SurfaceFluxRow>,
    pub radiometer_rows: Vec<RadiometerRow>,
    pub inverse_fit_rows: Vec<InverseFitRow>,
    pub solver_diagnostics: Vec<SolverDiagnostics>,
    pub summary: ReportSummary,
}
