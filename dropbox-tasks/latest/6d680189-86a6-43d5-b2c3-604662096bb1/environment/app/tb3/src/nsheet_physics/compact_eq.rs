use std::collections::BTreeMap;

use crate::{CvPoint, GeometryRow, GeometryRollup, IvPoint, CalibrationTapeout};

/// Threshold voltage at the measurement temperature.
pub fn vth_at_temp(params: &BTreeMap<String, f64>, temp_c: f64, ref_temp: f64) -> f64 {
    let _ = (params, temp_c, ref_temp);
    unimplemented!()
}

/// Mobility at the measurement temperature.
pub fn u0_at_temp(params: &BTreeMap<String, f64>, temp_c: f64, ref_temp: f64) -> f64 {
    let _ = (params, temp_c, ref_temp);
    unimplemented!()
}

pub fn weff(geom: &GeometryRow) -> f64 {
    geom.w_nm * geom.nfin as f64 * 1e-9
}

pub fn leff(geom: &GeometryRow) -> f64 {
    geom.l_nm * 1e-9
}

pub fn contact_for_geometry(tapeout: &CalibrationTapeout, geometry_id: &str) -> f64 {
    tapeout.contacts.get(geometry_id).copied().unwrap_or(0.0)
}

/// Drain-current compact model prediction.
pub fn id_model(
    params: &BTreeMap<String, f64>,
    vgs: f64,
    vds: f64,
    geom: &GeometryRow,
    temp_c: f64,
    ref_temp: f64,
    r_contact: f64,
) -> f64 {
    let _ = (params, vgs, vds, geom, temp_c, ref_temp, r_contact);
    unimplemented!()
}

/// Gate-capacitance compact model prediction.
pub fn cgg_model(
    params: &BTreeMap<String, f64>,
    vgs: f64,
    geom: &GeometryRow,
    temp_c: f64,
    ref_temp: f64,
) -> f64 {
    let _ = (params, vgs, geom, temp_c, ref_temp);
    unimplemented!()
}

pub fn group_geometries<'a>(
    tapeout: &'a CalibrationTapeout,
    split_group: &str,
) -> Vec<&'a GeometryRow> {
    tapeout
        .geometries
        .iter()
        .filter(|g| g.split_group == split_group)
        .collect()
}

pub fn iv_for_group<'a>(tapeout: &'a CalibrationTapeout, split_group: &str) -> Vec<&'a IvPoint> {
    let ids: Vec<String> = group_geometries(tapeout, split_group)
        .iter()
        .map(|g| g.geometry_id.clone())
        .collect();
    tapeout
        .iv_points
        .iter()
        .filter(|p| ids.contains(&p.geometry_id))
        .collect()
}

pub fn cv_for_group<'a>(tapeout: &'a CalibrationTapeout, split_group: &str) -> Vec<&'a CvPoint> {
    let ids: Vec<String> = group_geometries(tapeout, split_group)
        .iter()
        .map(|g| g.geometry_id.clone())
        .collect();
    tapeout
        .cv_points
        .iter()
        .filter(|p| ids.contains(&p.geometry_id))
        .collect()
}

/// Root-mean-square Id error for one split group in amperes.
pub fn rmse_id(
    params: &BTreeMap<String, f64>,
    tapeout: &CalibrationTapeout,
    rollup: &GeometryRollup,
    split_group: &str,
) -> f64 {
    let _ = (params, tapeout, rollup, split_group);
    unimplemented!()
}

/// Root-mean-square Cgg error for one split group in farads.
pub fn rmse_cv(
    params: &BTreeMap<String, f64>,
    tapeout: &CalibrationTapeout,
    rollup: &GeometryRollup,
    split_group: &str,
) -> f64 {
    let _ = (params, tapeout, rollup, split_group);
    unimplemented!()
}

/// Combined IV/CV objective used to drive coordinate descent.
pub fn combined_rmse(
    params: &BTreeMap<String, f64>,
    tapeout: &CalibrationTapeout,
    rollup: &GeometryRollup,
    split_group: &str,
) -> f64 {
    let _ = (params, tapeout, rollup, split_group);
    unimplemented!()
}

