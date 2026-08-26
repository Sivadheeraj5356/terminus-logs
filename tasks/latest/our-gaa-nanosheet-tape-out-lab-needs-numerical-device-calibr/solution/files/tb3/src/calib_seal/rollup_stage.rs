use sha2::{Digest, Sha256};

use crate::{
    CalibrationTapeout, GeometryRollup, RollupEntry, SCHEMA_ROLLUP, round6,
};

pub fn build_rollup(tapeout: &CalibrationTapeout) -> GeometryRollup {
    let mut iv_counts: std::collections::BTreeMap<String, u32> = std::collections::BTreeMap::new();
    let mut cv_counts: std::collections::BTreeMap<String, u32> = std::collections::BTreeMap::new();
    for point in &tapeout.iv_points {
        *iv_counts.entry(point.geometry_id.clone()).or_insert(0) += 1;
    }
    for point in &tapeout.cv_points {
        *cv_counts.entry(point.geometry_id.clone()).or_insert(0) += 1;
    }
    let mut entries = Vec::new();
    for geom in &tapeout.geometries {
        let aspect = round6((geom.w_nm * geom.nfin as f64) / geom.l_nm);
        let iv_n = iv_counts.get(&geom.geometry_id).copied().unwrap_or(0);
        let cv_n = cv_counts.get(&geom.geometry_id).copied().unwrap_or(0);
        entries.push(RollupEntry {
            geometry_id: geom.geometry_id.clone(),
            split_group: geom.split_group.clone(),
            aspect_weight: aspect,
            iv_weight: round6(aspect * iv_n as f64),
            cv_weight: round6(aspect * cv_n as f64),
        });
    }
    entries.sort_by(|a, b| a.geometry_id.cmp(&b.geometry_id));
    let digest = rollup_digest(&entries);
    GeometryRollup {
        schema_version: SCHEMA_ROLLUP.to_string(),
        reference_temp_c: tapeout.reference_temp_c,
        measure_digest: tapeout.measure_digest.clone(),
        entries,
        rollup_digest: digest,
    }
}

fn float_bits(value: f64) -> String {
    format!("{:016x}", value.to_bits())
}

fn rollup_digest(entries: &[RollupEntry]) -> String {
    let mut lines = Vec::new();
    for entry in entries {
        lines.push(format!(
            "entry|{}|{}|{}|{}|{}",
            entry.geometry_id,
            entry.split_group,
            float_bits(entry.aspect_weight),
            float_bits(entry.iv_weight),
            float_bits(entry.cv_weight),
        ));
    }
    let mut hasher = Sha256::new();
    hasher.update(lines.join("\n").as_bytes());
    format!("{:x}", hasher.finalize())
}

pub fn write_rollup(path: &std::path::Path, rollup: &GeometryRollup) -> Result<(), String> {
    use std::io::Write;
    let raw = serde_json::to_string_pretty(rollup).map_err(|e| e.to_string())?;
    let parent = match path.parent() {
        Some(dir) if !dir.as_os_str().is_empty() => dir.to_path_buf(),
        _ => std::path::PathBuf::from("."),
    };
    let file_name = path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("geometry_rollup.json");
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

pub fn read_rollup(path: &std::path::Path) -> Result<GeometryRollup, String> {
    let raw = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&raw).map_err(|e| e.to_string())
}

pub fn weight_maps(
    rollup: &GeometryRollup,
) -> (
    std::collections::BTreeMap<String, f64>,
    std::collections::BTreeMap<String, f64>,
) {
    let mut iv = std::collections::BTreeMap::new();
    let mut cv = std::collections::BTreeMap::new();
    for entry in &rollup.entries {
        iv.insert(entry.geometry_id.clone(), entry.iv_weight);
        cv.insert(entry.geometry_id.clone(), entry.cv_weight);
    }
    (iv, cv)
}
