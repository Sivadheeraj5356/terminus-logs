use crate::density;
use crate::enrichment;
use crate::model::{RegionBounds, XrfBound, round6};

/// Intersect density-band points with corrected XRF bounds.
pub fn intersect_region(
    density_points: &[(f64, f64, f64)],
    xrf: &XrfBound,
) -> (Vec<(f64, f64, f64)>, Option<RegionBounds>) {
    let mut hit = Vec::new();
    for &(a, g, c) in density_points {
        if enrichment::point_in_xrf_bound(a, g, c, xrf) {
            hit.push((a, g, c));
        }
    }
    if hit.is_empty() {
        return (hit, None);
    }
    let n = hit.len() as f64;
    let mut au = 0.0;
    let mut ag = 0.0;
    let mut cu = 0.0;
    for &(a, g, c) in &hit {
        au += a;
        ag += g;
        cu += c;
    }
    au = round6(au / n);
    ag = round6(ag / n);
    cu = round6(cu / n);
    let region = RegionBounds {
        f_au_min: au,
        f_au_max: au,
        f_ag_min: ag,
        f_ag_max: ag,
        f_cu_min: cu,
        f_cu_max: cu,
    };
    let _ = density::region_from_points;
    (hit, Some(region))
}
