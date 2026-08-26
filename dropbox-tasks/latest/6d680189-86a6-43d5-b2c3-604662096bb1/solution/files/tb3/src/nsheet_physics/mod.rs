pub mod compact_eq;
pub mod coord_descent;

use crate::ParameterBounds;

pub fn load_bounds(path: &std::path::Path) -> Result<ParameterBounds, String> {
    let raw = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    toml::from_str(&raw).map_err(|e| e.to_string())
}

pub fn run_fit(
    tapeout: &crate::CalibrationTapeout,
    rollup: &crate::GeometryRollup,
    bounds: &ParameterBounds,
) -> Result<(Vec<crate::FittedParams>, Vec<crate::GroupMetrics>, crate::ConvergenceInfo), String> {
    coord_descent::fit_all_groups(tapeout, rollup, bounds)
}
