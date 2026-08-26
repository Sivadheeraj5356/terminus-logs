//! Legacy linear mass-mixing helpers. Not on the assay hot path.
#![allow(dead_code)]
use crate::model::MetalDensities;

pub fn linear_alloy_density(f_au: f64, f_ag: f64, f_cu: f64, metals: &MetalDensities) -> f64 {
    f_au * metals.rho_au + f_ag * metals.rho_ag + f_cu * metals.rho_cu
}

pub fn naive_surface_as_bulk(f_au: f64, f_ag: f64, f_cu: f64) -> (f64, f64, f64) {
    (f_au, f_ag, f_cu)
}
