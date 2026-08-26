use crate::GeometryRow;
use serde::Deserialize;
use std::path::Path;

#[derive(Debug, Deserialize)]
struct Manifest {
    schema_version: String,
    reference_temp_c: f64,
    geometries: Vec<GeometryRowRaw>,
}

#[derive(Debug, Deserialize)]
struct GeometryRowRaw {
    geometry_id: String,
    #[serde(rename = "L_nm")]
    l_nm: f64,
    #[serde(rename = "W_nm")]
    w_nm: f64,
    nfin: u32,
    split_group: String,
}

pub fn load_geometry_manifest(path: &Path) -> Result<(Vec<GeometryRow>, f64), String> {
    let raw = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    let manifest: Manifest = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    if manifest.schema_version != "gaa-geometry-v1" {
        return Err("unsupported geometry schema".to_string());
    }
    let mut geometries = Vec::new();
    for row in manifest.geometries {
        geometries.push(GeometryRow {
            geometry_id: row.geometry_id,
            l_nm: row.l_nm,
            w_nm: row.w_nm,
            nfin: row.nfin,
            split_group: row.split_group,
        });
    }
    Ok((geometries, manifest.reference_temp_c))
}

pub fn sort_geometry_rows(geometries: &[GeometryRow]) -> Vec<GeometryRow> {
    let mut rows = geometries.to_vec();
    rows.sort_by(|a, b| a.geometry_id.cmp(&b.geometry_id));
    rows
}


