use crate::density;
use crate::enrichment;
use crate::model::{RegionBounds, XrfBound};

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
    let region = density::region_from_points(&hit);
    (hit, region)
}
