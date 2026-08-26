//! Atomic JSON report writing — incomplete starter (serialization helpers only).

use crate::error::{SolverError, SolverResult};
use crate::model::SolverReport;
use std::fs;
use std::path::Path;

pub fn write_report_atomic(_path: &Path, _report: &SolverReport) -> SolverResult<()> {
    Err(SolverError::new(
        "full report assembly is not implemented; parsers and structs only",
    ))
}

pub fn round_f64(value: f64, places: i32) -> f64 {
    if !value.is_finite() {
        return value;
    }
    let factor = 10f64.powi(places);
    (value * factor).round() / factor
}

pub fn remove_stale_outputs(output: &Path) {
    let _ = fs::remove_file(output);
    let tmp = output.with_extension("tmp");
    let _ = fs::remove_file(tmp);
}
