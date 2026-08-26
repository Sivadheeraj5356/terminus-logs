use std::collections::BTreeMap;

use crate::calib_seal::rollup_stage::weight_maps;
use crate::{CvPoint, GeometryRow, GeometryRollup, IvPoint, CalibrationTapeout, VT, round12};

pub fn vth_at_temp(params: &BTreeMap<String, f64>, temp_c: f64, ref_temp: f64) -> f64 {
    params["vth0"] + params["kt1"] * (temp_c - ref_temp)
}

pub fn u0_at_temp(params: &BTreeMap<String, f64>, temp_c: f64, ref_temp: f64) -> f64 {
    let ratio = (temp_c + 273.15) / (ref_temp + 273.15);
    params["u0"] * ratio.powf(params["ute"])
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

pub fn id_model(
    params: &BTreeMap<String, f64>,
    vgs: f64,
    vds: f64,
    geom: &GeometryRow,
    temp_c: f64,
    ref_temp: f64,
    r_contact: f64,
) -> f64 {
    let vth = vth_at_temp(params, temp_c, ref_temp);
    let u0 = u0_at_temp(params, temp_c, ref_temp);
    let w = weff(geom);
    let l = leff(geom);
    let ratio = w / l;
    let mut id_val = 0.0;
    for _ in 0..6 {
        let vds_eff = (vds - id_val * r_contact).max(0.0);
        if vgs < vth {
            let arg = (vgs - vth) / (params["ss_factor"] * VT);
            id_val =
                params["subth_weight"] * ratio * arg.exp() * (1.0 - (-vds_eff / VT).exp());
        } else {
            let cox = 2.0 * params["cgso"] / w;
            let vgt = (vgs - vth).max(0.0);
            let body = 1.0 + params["k1"] * vgt.sqrt();
            id_val = u0 * cox * ratio * (vgt * vds_eff - 0.5 * vds_eff * vds_eff) * body;
        }
        id_val = id_val.max(0.0);
    }
    round12(id_val)
}

pub fn cgg_model(
    params: &BTreeMap<String, f64>,
    vgs: f64,
    geom: &GeometryRow,
    temp_c: f64,
    ref_temp: f64,
) -> f64 {
    let vth = vth_at_temp(params, temp_c, ref_temp);
    let w = weff(geom);
    let l = leff(geom);
    let cox = 2.0 * params["cgso"] / w;
    let mut cgg = cox * w * l;
    if vgs < vth {
        let arg = (vgs - vth) / (params["ss_factor"] * VT);
        cgg *= 0.55 + 0.45 * arg.exp();
    }
    round12(cgg)
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

pub fn rmse_id(
    params: &BTreeMap<String, f64>,
    tapeout: &CalibrationTapeout,
    rollup: &GeometryRollup,
    split_group: &str,
) -> f64 {
    let (iv_weights, _) = weight_maps(rollup);
    let geoms: BTreeMap<String, &GeometryRow> = group_geometries(tapeout, split_group)
        .into_iter()
        .map(|g| (g.geometry_id.clone(), g))
        .collect();
    let mut sum = 0.0_f64;
    let mut weight_sum = 0.0_f64;
    for point in iv_for_group(tapeout, split_group) {
        let geom = geoms[&point.geometry_id];
        let r = contact_for_geometry(tapeout, &point.geometry_id);
        let pred = id_model(
            params,
            point.vgs,
            point.vds,
            geom,
            point.temp_c,
            tapeout.reference_temp_c,
            r,
        );
        let err = point.id_amps - pred;
        let w = iv_weights.get(&point.geometry_id).copied().unwrap_or(0.0);
        sum += w * err * err;
        weight_sum += w;
    }
    (sum / weight_sum).sqrt()
}

pub fn rmse_cv(
    params: &BTreeMap<String, f64>,
    tapeout: &CalibrationTapeout,
    rollup: &GeometryRollup,
    split_group: &str,
) -> f64 {
    let (_, cv_weights) = weight_maps(rollup);
    let geoms: BTreeMap<String, &GeometryRow> = group_geometries(tapeout, split_group)
        .into_iter()
        .map(|g| (g.geometry_id.clone(), g))
        .collect();
    let mut sum = 0.0_f64;
    let mut weight_sum = 0.0_f64;
    for point in cv_for_group(tapeout, split_group) {
        let geom = geoms[&point.geometry_id];
        let pred = cgg_model(params, point.vgs, geom, point.temp_c, tapeout.reference_temp_c);
        let err = point.cgg_f - pred;
        let w = cv_weights.get(&point.geometry_id).copied().unwrap_or(0.0);
        sum += w * err * err;
        weight_sum += w;
    }
    (sum / weight_sum).sqrt()
}

pub fn combined_rmse(
    params: &BTreeMap<String, f64>,
    tapeout: &CalibrationTapeout,
    rollup: &GeometryRollup,
    split_group: &str,
) -> f64 {
    let id = rmse_id(params, tapeout, rollup, split_group);
    let cv = rmse_cv(params, tapeout, rollup, split_group);
    (id * id + cv * cv).sqrt()
}
