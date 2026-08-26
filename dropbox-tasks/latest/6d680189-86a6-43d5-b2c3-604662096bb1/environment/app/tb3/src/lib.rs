pub mod legacy_bsim;
pub mod foundry_card;
pub mod nsheet_physics;
pub mod lab_corpus;
pub mod calib_seal;

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const SCHEMA_TAPEOUT: &str = "gaa-tapeout-v1";
pub const SCHEMA_ROLLUP: &str = "gaa-rollup-v1";
pub const SCHEMA_VALIDATION: &str = "model-validation-v1";
pub const SCHEMA_SPICE: &str = "gaa-spice-v1";

pub const DEFAULT_DATA: &str = "/app/data/bundled";
pub const DEFAULT_BOUNDS: &str = "/app/config/parameter_bounds.toml";
pub const DEFAULT_TAPEOUT: &str = "/app/state/calibration_tapeout.json";
pub const DEFAULT_ROLLUP: &str = "/app/state/geometry_rollup.json";
pub const DEFAULT_SPICE: &str = "/app/out/gaa_model.sp";
pub const DEFAULT_VALIDATION: &str = "/app/out/model_validation.json";
pub const DEFAULT_REF_TEMP: f64 = 25.0;
pub const VT: f64 = 0.026;

pub const PARAM_NAMES: [&str; 9] = [
    "vth0", "u0", "ss_factor", "cgso", "rsd", "k1", "ute", "kt1", "subth_weight",
];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GeometryRow {
    pub geometry_id: String,
    pub l_nm: f64,
    pub w_nm: f64,
    pub nfin: u32,
    pub split_group: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IvPoint {
    pub geometry_id: String,
    pub vgs: f64,
    pub vds: f64,
    pub id_amps: f64,
    pub temp_c: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CvPoint {
    pub geometry_id: String,
    pub vgs: f64,
    pub cgg_f: f64,
    pub temp_c: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RollupEntry {
    pub geometry_id: String,
    pub split_group: String,
    pub aspect_weight: f64,
    pub iv_weight: f64,
    pub cv_weight: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GeometryRollup {
    pub schema_version: String,
    pub reference_temp_c: f64,
    pub measure_digest: String,
    pub entries: Vec<RollupEntry>,
    pub rollup_digest: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CalibrationTapeout {
    pub schema_version: String,
    pub reference_temp_c: f64,
    pub geometries: Vec<GeometryRow>,
    pub iv_points: Vec<IvPoint>,
    pub cv_points: Vec<CvPoint>,
    pub contacts: BTreeMap<String, f64>,
    pub measure_digest: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParamSpec {
    pub min: f64,
    pub max: f64,
    pub initial: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SolverPolicy {
    pub max_iterations: u32,
    pub step_fraction: f64,
    pub convergence_rmse: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SharedGroup {
    pub tie_break_order: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParameterBounds {
    pub schema_version: String,
    pub reference: ReferenceBlock,
    pub solver: SolverPolicy,
    pub parameters: BTreeMap<String, ParamSpec>,
    pub shared_groups: BTreeMap<String, SharedGroup>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReferenceBlock {
    pub temp_c: f64,
    pub vt: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FittedParams {
    pub split_group: String,
    pub values: BTreeMap<String, f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConvergenceInfo {
    pub iterations: u32,
    pub final_rmse: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GroupMetrics {
    pub split_group: String,
    pub id_rmse: f64,
    pub cv_rmse: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelValidation {
    pub schema_version: String,
    pub reference_temp_c: f64,
    pub rollup_digest: String,
    pub fitted_groups: Vec<FittedParams>,
    pub group_metrics: Vec<GroupMetrics>,
    pub convergence: ConvergenceInfo,
    pub validation_digest: String,
}

pub fn resolve_data_root(data_dir: &str) -> Result<std::path::PathBuf, String> {
    if let Ok(overlay) = std::env::var("TB3_GAA_DATA_ROOT") {
        if !overlay.is_empty() {
            if !overlay.starts_with('/') {
                return Err("TB3_GAA_DATA_ROOT must be absolute".to_string());
            }
            return Ok(std::path::PathBuf::from(overlay));
        }
    }
    let path = std::path::PathBuf::from(data_dir);
    if !path.is_absolute() {
        return Err("data directory must be absolute".to_string());
    }
    Ok(path)
}

pub fn resolve_iv_path(data_dir: &str) -> Result<std::path::PathBuf, String> {
    Ok(resolve_data_root(data_dir)?.join("iv_sweep.csv"))
}

pub fn resolve_cv_path(data_dir: &str) -> Result<std::path::PathBuf, String> {
    Ok(resolve_data_root(data_dir)?.join("cv_sweep.csv"))
}

pub fn resolve_geometry_path(data_dir: &str) -> Result<std::path::PathBuf, String> {
    Ok(resolve_data_root(data_dir)?.join("geometry_manifest.json"))
}

pub fn resolve_contact_path(data_dir: &str) -> Result<std::path::PathBuf, String> {
    Ok(resolve_data_root(data_dir)?.join("contact_resistance.json"))
}

pub fn resolve_bounds_path(default_path: &str) -> Result<std::path::PathBuf, String> {
    if let Ok(overlay) = std::env::var("TB3_GAA_BOUNDS_ROOT") {
        if !overlay.is_empty() {
            if !overlay.starts_with('/') {
                return Err("TB3_GAA_BOUNDS_ROOT must be absolute".to_string());
            }
            return Ok(std::path::PathBuf::from(overlay).join("parameter_bounds.toml"));
        }
    }
    Ok(std::path::PathBuf::from(default_path))
}

pub fn round6(value: f64) -> f64 {
    (value * 1_000_000.0).round() / 1_000_000.0
}

pub fn round9(value: f64) -> f64 {
    (value * 1_000_000_000.0).round() / 1_000_000_000.0
}

pub fn round12(value: f64) -> f64 {
    if value == 0.0 {
        return 0.0;
    }
    let exp = value.abs().log10().floor() as i32;
    let scale = 10_f64.powi(11 - exp);
    (value * scale).round_ties_even() / scale
}

/// Match Python f-string float rendering used in validation digests.
pub fn format_digest_float(value: f64) -> String {
    if value == 0.0 {
        return "0.0".to_string();
    }
    let rendered = format!("{value}");
    if !rendered.contains('.') && !rendered.contains('e') && !rendered.contains('E') {
        format!("{rendered}.0")
    } else {
        rendered
    }
}

/// Match Python `{value:.12e}` exponent width in SPICE cards.
pub fn format_py_sci(value: f64) -> String {
    let rendered = format!("{value:.12e}");
    let Some(idx) = rendered.find('e') else {
        return rendered;
    };
    let (mantissa, _) = rendered.split_at(idx);
    let exponent: i32 = rendered[idx + 1..].parse().unwrap_or(0);
    format!("{mantissa}e{exponent:+03}")
}






