//! Raw lab-measurement loaders.
//!
//! This module loads the raw device-characterization corpus (IV sweep, CV
//! sweep, geometry manifest, and contact-resistance records) from disk and
//! keeps the parsed rows in memory for the downstream fit and card-publish
//! steps. `load_bundle` loads the full corpus; `read_manifest_only`
//! loads just the geometry manifest for reference-temperature lookups.

pub mod contact;
pub mod cv;
pub mod geometry;
pub mod iv;

use crate::lab_corpus::contact::load_contacts;
use crate::lab_corpus::cv::load_cv_sweep;
use crate::lab_corpus::geometry::load_geometry_manifest;
use crate::lab_corpus::iv::load_iv_sweep;
use std::path::Path;

pub fn load_bundle(data_dir: &str) -> Result<(Vec<crate::GeometryRow>, Vec<crate::IvPoint>, Vec<crate::CvPoint>, std::collections::BTreeMap<String, f64>, f64), String> {
    let iv_path = crate::resolve_iv_path(data_dir)?;
    let cv_path = crate::resolve_cv_path(data_dir)?;
    let geom_path = crate::resolve_geometry_path(data_dir)?;
    let contact_path = crate::resolve_contact_path(data_dir)?;
    let (geometries, ref_temp) = load_geometry_manifest(&geom_path)?;
    let iv_points = load_iv_sweep(&iv_path)?;
    let cv_points = load_cv_sweep(&cv_path)?;
    let contacts = load_contacts(&contact_path)?;
    Ok((geometries, iv_points, cv_points, contacts, ref_temp))
}

pub fn read_manifest_only(data_dir: &str) -> Result<f64, String> {
    let geom_path = crate::resolve_geometry_path(data_dir)?;
    let (_, ref_temp) = load_geometry_manifest(&geom_path)?;
    Ok(ref_temp)
}

pub fn file_exists(path: &Path) -> bool {
    path.is_file()
}
