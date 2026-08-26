use sha2::{Digest, Sha256};

use crate::lab_corpus::geometry::sort_geometry_rows;
use crate::{CvPoint, GeometryRow, IvPoint, CalibrationTapeout, SCHEMA_TAPEOUT, round12};

pub fn build_tapeout(
    geometries: Vec<GeometryRow>,
    mut iv_points: Vec<IvPoint>,
    mut cv_points: Vec<CvPoint>,
    contacts: std::collections::BTreeMap<String, f64>,
    reference_temp_c: f64,
) -> CalibrationTapeout {
    iv_points.sort_by(|a, b| {
        a.geometry_id
            .cmp(&b.geometry_id)
            .then_with(|| a.vgs.total_cmp(&b.vgs))
            .then_with(|| a.vds.total_cmp(&b.vds))
    });
    cv_points.sort_by(|a, b| {
        a.geometry_id
            .cmp(&b.geometry_id)
            .then_with(|| a.vgs.total_cmp(&b.vgs))
    });
    let sorted_geometries = sort_geometry_rows(&geometries);
    let digest = measure_digest(&iv_points, &cv_points);
    CalibrationTapeout {
        schema_version: SCHEMA_TAPEOUT.to_string(),
        reference_temp_c,
        geometries: sorted_geometries,
        iv_points,
        cv_points,
        contacts,
        measure_digest: digest,
    }
}

fn float_bits(value: f64) -> String {
    format!("{:016x}", value.to_bits())
}

fn measure_digest(iv_points: &[IvPoint], cv_points: &[CvPoint]) -> String {
    let mut lines = Vec::new();
    for point in iv_points {
        lines.push(format!(
            "iv|{}|{}|{}|{}|{}",
            point.geometry_id,
            float_bits(point.vgs),
            float_bits(point.vds),
            float_bits(point.id_amps),
            float_bits(point.temp_c)
        ));
    }
    for point in cv_points {
        lines.push(format!(
            "cv|{}|{}|{}|{}",
            point.geometry_id,
            float_bits(point.vgs),
            float_bits(point.cgg_f),
            float_bits(point.temp_c)
        ));
    }
    let mut hasher = Sha256::new();
    hasher.update(lines.join("\n").as_bytes());
    format!("{:x}", hasher.finalize())
}

pub fn write_tapeout(path: &std::path::Path, tapeout: &CalibrationTapeout) -> Result<(), String> {
    use std::io::Write;
    let raw = serde_json::to_string_pretty(tapeout).map_err(|e| e.to_string())?;
    let parent = match path.parent() {
        Some(dir) if !dir.as_os_str().is_empty() => dir.to_path_buf(),
        _ => std::path::PathBuf::from("."),
    };
    let file_name = path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("calibration_tapeout.json");
    let tmp_path = parent.join(format!(".{file_name}.tmp"));
    {
        let mut tmp = std::fs::File::create(&tmp_path).map_err(|e| e.to_string())?;
        tmp.write_all(raw.as_bytes()).map_err(|e| e.to_string())?;
        tmp.write_all(b"\n").map_err(|e| e.to_string())?;
        tmp.flush().map_err(|e| e.to_string())?;
        tmp.sync_all().map_err(|e| e.to_string())?;
    }
    std::fs::rename(&tmp_path, path).map_err(|e| e.to_string())
}

pub fn read_tapeout(path: &std::path::Path) -> Result<CalibrationTapeout, String> {
    let raw = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&raw).map_err(|e| e.to_string())
}

pub fn normalize_tapeout_points(tapeout: &mut CalibrationTapeout) {
    for point in &mut tapeout.iv_points {
        point.id_amps = round12(point.id_amps);
    }
    for point in &mut tapeout.cv_points {
        point.cgg_f = round12(point.cgg_f);
    }
}


