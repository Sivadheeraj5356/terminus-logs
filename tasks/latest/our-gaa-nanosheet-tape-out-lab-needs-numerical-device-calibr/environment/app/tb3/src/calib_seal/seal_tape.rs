use crate::{CvPoint, GeometryRow, IvPoint, CalibrationTapeout};

/// Build the persisted calibration snapshot from instrument measurement rows.
pub fn build_tapeout(
    geometries: Vec<GeometryRow>,
    iv_points: Vec<IvPoint>,
    cv_points: Vec<CvPoint>,
    contacts: std::collections::BTreeMap<String, f64>,
    reference_temp_c: f64,
) -> CalibrationTapeout {
    let _ = (geometries, iv_points, cv_points, contacts, reference_temp_c);
    unimplemented!()
}

/// Persist the tapeout snapshot to disk.
pub fn write_tapeout(path: &std::path::Path, tapeout: &CalibrationTapeout) -> Result<(), String> {
    let _ = (path, tapeout);
    unimplemented!()
}

pub fn read_tapeout(path: &std::path::Path) -> Result<CalibrationTapeout, String> {
    let raw = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&raw).map_err(|e| e.to_string())
}


