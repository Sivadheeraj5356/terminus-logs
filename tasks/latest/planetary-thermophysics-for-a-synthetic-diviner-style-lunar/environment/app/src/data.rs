//! Loading of every CSV/JSON input file that describes the regolith column,
//! illumination history, radiometer bands and inversion queries.

use crate::error::{SolverError, SolverResult};
use serde::Deserialize;
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Deserialize)]
pub struct SolverConfig {
    pub stefan_boltzmann_w_m2_k4: f64,
    pub planck_constant_j_s: f64,
    pub boltzmann_constant_j_k: f64,
    pub speed_of_light_m_s: f64,
    pub time_step_s: f64,
    pub nonlinear_temperature_tolerance_k: f64,
    pub nonlinear_residual_tolerance_w_m2: f64,
    pub nonlinear_max_iterations: i64,
    pub line_search_min_factor: f64,
    pub minimum_temperature_k: f64,
    pub maximum_temperature_k: f64,
    pub energy_balance_tolerance_j_m2: f64,
    pub brightness_temperature_tolerance_k: f64,
    pub brightness_temperature_max_iterations: i64,
    pub inversion_parameter_tolerance: f64,
    pub inversion_objective_tolerance: f64,
    pub inversion_max_evaluations: i64,
    pub output_decimal_places: i32,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Material {
    pub material_id: String,
    pub density_kg_m3: f64,
    pub heat_capacity_c0_j_kg_k: f64,
    pub heat_capacity_c1_j_kg_k2: f64,
    pub heat_capacity_c2_j_kg_k3: f64,
    pub contact_conductivity_w_m_k: f64,
    pub conductivity_depth_gradient_per_m: f64,
    pub radiative_conductivity_w_m_k4: f64,
    pub surface_albedo: f64,
    pub surface_emissivity: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct GridCell {
    pub case_id: String,
    pub cell_index: i64,
    pub top_depth_m: f64,
    pub bottom_depth_m: f64,
    pub material_id: String,
    pub initial_temperature_k: f64,
}

impl GridCell {
    pub fn center_depth_m(&self) -> f64 {
        0.5 * (self.top_depth_m + self.bottom_depth_m)
    }

    pub fn thickness_m(&self) -> f64 {
        self.bottom_depth_m - self.top_depth_m
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct IlluminationCase {
    pub case_id: String,
    pub period_s: f64,
    pub solar_flux_w_m2: f64,
    pub geothermal_flux_w_m2: f64,
    pub conductivity_scale: f64,
    pub albedo_offset: f64,
    pub spinup_tolerance_k: f64,
    pub maximum_spinup_cycles: i64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ForcingInterval {
    pub case_id: String,
    pub interval_seq: i64,
    pub start_time_s: f64,
    pub end_time_s: f64,
    pub cos_incidence_start: f64,
    pub cos_incidence_end: f64,
    pub eclipse_profile_id: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct EclipsePoint {
    pub eclipse_profile_id: String,
    pub profile_time_s: f64,
    pub transmission_fraction: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct BandSample {
    pub band_id: String,
    pub sample_index: i64,
    pub wavelength_um: f64,
    pub response: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ObservationQuery {
    pub observation_id: String,
    pub case_id: String,
    pub time_s: f64,
    pub band_id: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct InversionFit {
    pub fit_id: String,
    pub case_id: String,
    pub parameter_names: Vec<String>,
    pub lower_bounds: Vec<f64>,
    pub upper_bounds: Vec<f64>,
    pub initial_values: Vec<f64>,
    pub observation_ids: Vec<String>,
    pub target_brightness_temperatures_k: Vec<f64>,
    pub observation_weights: Vec<f64>,
}

#[derive(Debug, Deserialize)]
struct InversionFitsWrapper {
    fits: Vec<InversionFit>,
}

pub struct SolverData {
    pub config: SolverConfig,
    pub materials: HashMap<String, Material>,
    pub grid_cells: HashMap<String, Vec<GridCell>>,
    pub illumination_cases: HashMap<String, IlluminationCase>,
    pub forcing_intervals: HashMap<String, Vec<ForcingInterval>>,
    pub eclipse_profiles: HashMap<String, Vec<EclipsePoint>>,
    pub radiometer_bands: HashMap<String, Vec<BandSample>>,
    pub observation_queries: Vec<ObservationQuery>,
    pub inversion_fits: Vec<InversionFit>,
}

impl SolverData {
    pub fn material(&self, material_id: &str) -> SolverResult<&Material> {
        self.materials
            .get(material_id)
            .ok_or_else(|| SolverError::new(format!("Missing material id: {material_id}")))
    }

    pub fn cells_for_case(&self, case_id: &str) -> SolverResult<&Vec<GridCell>> {
        self.grid_cells
            .get(case_id)
            .ok_or_else(|| SolverError::new(format!("Missing depth grid for case: {case_id}")))
    }

    pub fn intervals_for_case(&self, case_id: &str) -> SolverResult<&Vec<ForcingInterval>> {
        self.forcing_intervals.get(case_id).ok_or_else(|| {
            SolverError::new(format!("Missing forcing intervals for case: {case_id}"))
        })
    }

    pub fn eclipse_points(&self, profile_id: &str) -> SolverResult<&Vec<EclipsePoint>> {
        self.eclipse_profiles.get(profile_id).ok_or_else(|| {
            SolverError::new(format!("Missing eclipse profile: {profile_id}"))
        })
    }

    pub fn band(&self, band_id: &str) -> SolverResult<&Vec<BandSample>> {
        self.radiometer_bands
            .get(band_id)
            .ok_or_else(|| SolverError::new(format!("Missing radiometer band: {band_id}")))
    }
}

pub fn load_solver_config(path: &Path) -> SolverResult<SolverConfig> {
    let text = fs::read_to_string(path)
        .map_err(|e| SolverError::new(format!("Failed to read {}: {e}", path.display())))?;
    serde_json::from_str(&text)
        .map_err(|e| SolverError::new(format!("Failed to parse {}: {e}", path.display())))
}

fn read_csv<T: serde::de::DeserializeOwned>(path: &Path) -> SolverResult<Vec<T>> {
    let mut reader = csv::Reader::from_path(path)
        .map_err(|e| SolverError::new(format!("Failed to open {}: {e}", path.display())))?;
    let mut rows = Vec::new();
    for result in reader.deserialize() {
        let record: T = result
            .map_err(|e| SolverError::new(format!("CSV parse error in {}: {e}", path.display())))?;
        rows.push(record);
    }
    Ok(rows)
}

fn load_inversion_fits(path: &Path) -> SolverResult<Vec<InversionFit>> {
    if !path.is_file() {
        return Ok(Vec::new());
    }
    let text = fs::read_to_string(path)
        .map_err(|e| SolverError::new(format!("Failed to read {}: {e}", path.display())))?;
    if let Ok(wrapper) = serde_json::from_str::<InversionFitsWrapper>(&text) {
        return Ok(wrapper.fits);
    }
    serde_json::from_str::<Vec<InversionFit>>(&text)
        .map_err(|e| SolverError::new(format!("Failed to parse {}: {e}", path.display())))
}

pub fn load_solver_data(data_dir: &Path) -> SolverResult<SolverData> {
    let config = load_solver_config(&data_dir.join("solver_config.json"))?;

    let mut materials: HashMap<String, Material> = HashMap::new();
    for material in read_csv::<Material>(&data_dir.join("materials.csv"))? {
        materials.insert(material.material_id.clone(), material);
    }

    let mut grid_cells: HashMap<String, Vec<GridCell>> = HashMap::new();
    for cell in read_csv::<GridCell>(&data_dir.join("depth_grid.csv"))? {
        grid_cells.entry(cell.case_id.clone()).or_default().push(cell);
    }
    for cells in grid_cells.values_mut() {
        cells.sort_by_key(|cell| cell.cell_index);
    }

    let mut illumination_cases: HashMap<String, IlluminationCase> = HashMap::new();
    for case in read_csv::<IlluminationCase>(&data_dir.join("illumination_cases.csv"))? {
        illumination_cases.insert(case.case_id.clone(), case);
    }

    let mut forcing_intervals: HashMap<String, Vec<ForcingInterval>> = HashMap::new();
    for interval in read_csv::<ForcingInterval>(&data_dir.join("forcing_intervals.csv"))? {
        forcing_intervals
            .entry(interval.case_id.clone())
            .or_default()
            .push(interval);
    }
    for intervals in forcing_intervals.values_mut() {
        intervals.sort_by_key(|interval| interval.interval_seq);
    }

    let mut eclipse_profiles: HashMap<String, Vec<EclipsePoint>> = HashMap::new();
    for point in read_csv::<EclipsePoint>(&data_dir.join("eclipse_profiles.csv"))? {
        eclipse_profiles
            .entry(point.eclipse_profile_id.clone())
            .or_default()
            .push(point);
    }
    for points in eclipse_profiles.values_mut() {
        points.sort_by(|a, b| {
            a.profile_time_s
                .partial_cmp(&b.profile_time_s)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
    }

    let mut radiometer_bands: HashMap<String, Vec<BandSample>> = HashMap::new();
    for sample in read_csv::<BandSample>(&data_dir.join("radiometer_bands.csv"))? {
        radiometer_bands
            .entry(sample.band_id.clone())
            .or_default()
            .push(sample);
    }
    for samples in radiometer_bands.values_mut() {
        samples.sort_by_key(|sample| sample.sample_index);
    }

    let observation_queries: Vec<ObservationQuery> =
        read_csv(&data_dir.join("observation_queries.csv"))?;

    let inversion_fits = load_inversion_fits(&data_dir.join("inversion_queries.json"))?;

    Ok(SolverData {
        config,
        materials,
        grid_cells,
        illumination_cases,
        forcing_intervals,
        eclipse_profiles,
        radiometer_bands,
        observation_queries,
        inversion_fits,
    })
}

pub fn default_data_dir() -> PathBuf {
    let app_data = PathBuf::from("/app/data");
    if app_data.join("solver_config.json").is_file() {
        return app_data;
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            let rel = dir.join("data");
            if rel.join("solver_config.json").is_file() {
                return rel;
            }
        }
    }
    PathBuf::from("data")
}
