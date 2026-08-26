use crate::model::{DensityBandSummary, MetalDensities, RegionBounds, round6};

/// Ideal volume-additive (harmonic) mixing density.
pub fn rho_ideal(f_au: f64, f_ag: f64, f_cu: f64, metals: &MetalDensities) -> f64 {
    let inv = f_au / metals.rho_au + f_ag / metals.rho_ag + f_cu / metals.rho_cu;
    1.0 / inv
}

pub fn rho_of(
    f_au: f64,
    f_ag: f64,
    f_cu: f64,
    mixing_rule: &str,
    kappa: Option<f64>,
    metals: &MetalDensities,
) -> f64 {
    let base = rho_ideal(f_au, f_ag, f_cu, metals);
    if mixing_rule == "nonideal" {
        let k = kappa.unwrap_or(0.0);
        base * (1.0 + k * f_au * f_cu)
    } else {
        base
    }
}

pub fn sample_simplex(grid_n: usize) -> Vec<(f64, f64, f64)> {
    let mut out = Vec::new();
    if grid_n < 2 {
        return out;
    }
    let n = grid_n - 1;
    for i in 0..=n {
        for j in 0..=(n - i) {
            let f_au = i as f64 / n as f64;
            let f_ag = j as f64 / n as f64;
            let f_cu = 1.0 - f_au - f_ag;
            if f_cu >= -1e-12 {
                out.push((f_au, f_ag, f_cu.max(0.0)));
            }
        }
    }
    out
}

pub fn density_band_points(
    rho_m: f64,
    sigma: f64,
    mixing_rule: &str,
    kappa: Option<f64>,
    metals: &MetalDensities,
    grid_n: usize,
) -> Result<Vec<(f64, f64, f64)>, String> {
    let pts = sample_simplex(grid_n);
    let mut band = Vec::new();
    for (a, g, c) in pts {
        let r = rho_of(a, g, c, mixing_rule, kappa, metals);
        if (r - rho_m).abs() <= sigma + 1e-12 {
            band.push((a, g, c));
        }
    }
    Ok(band)
}

pub fn summarize_points(points: &[(f64, f64, f64)]) -> Option<DensityBandSummary> {
    if points.is_empty() {
        return None;
    }
    let mut au_min = f64::INFINITY;
    let mut au_max = f64::NEG_INFINITY;
    let mut ag_min = f64::INFINITY;
    let mut ag_max = f64::NEG_INFINITY;
    let mut cu_min = f64::INFINITY;
    let mut cu_max = f64::NEG_INFINITY;
    for &(a, g, c) in points {
        au_min = au_min.min(a);
        au_max = au_max.max(a);
        ag_min = ag_min.min(g);
        ag_max = ag_max.max(g);
        cu_min = cu_min.min(c);
        cu_max = cu_max.max(c);
    }
    Some(DensityBandSummary {
        point_count: points.len(),
        f_au_min: round6(au_min),
        f_au_max: round6(au_max),
        f_ag_min: round6(ag_min),
        f_ag_max: round6(ag_max),
        f_cu_min: round6(cu_min),
        f_cu_max: round6(cu_max),
    })
}

pub fn region_from_points(points: &[(f64, f64, f64)]) -> Option<RegionBounds> {
    let s = summarize_points(points)?;
    Some(RegionBounds {
        f_au_min: s.f_au_min,
        f_au_max: s.f_au_max,
        f_ag_min: s.f_ag_min,
        f_ag_max: s.f_ag_max,
        f_cu_min: s.f_cu_min,
        f_cu_max: s.f_cu_max,
    })
}
