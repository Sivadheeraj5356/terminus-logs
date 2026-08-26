use crate::{CalibrationTapeout, GeometryRollup};

/// Build geometry rollup weights from a sealed calibration tapeout.
pub fn build_rollup(tapeout: &CalibrationTapeout) -> GeometryRollup {
    let _ = tapeout;
    unimplemented!()
}

/// Persist the geometry rollup artifact to disk.
pub fn write_rollup(path: &std::path::Path, rollup: &GeometryRollup) -> Result<(), String> {
    let _ = (path, rollup);
    unimplemented!()
}

pub fn read_rollup(path: &std::path::Path) -> Result<GeometryRollup, String> {
    let raw = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&raw).map_err(|e| e.to_string())
}
