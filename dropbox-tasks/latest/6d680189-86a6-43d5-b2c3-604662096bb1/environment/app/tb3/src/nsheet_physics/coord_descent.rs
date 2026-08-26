use std::collections::BTreeMap;

use crate::{ConvergenceInfo, FittedParams, GeometryRollup, GroupMetrics, CalibrationTapeout, ParameterBounds};

/// Fit every split group and assemble per-group metrics and convergence data.
pub fn fit_all_groups(
    tapeout: &CalibrationTapeout,
    rollup: &GeometryRollup,
    bounds: &ParameterBounds,
) -> Result<(Vec<FittedParams>, Vec<GroupMetrics>, ConvergenceInfo), String> {
    let _ = (tapeout, rollup, bounds);
    unimplemented!()
}

/// Coordinate-descent optimizer for a single split group.
#[allow(dead_code)]
fn coordinate_descent(
    tapeout: &CalibrationTapeout,
    rollup: &GeometryRollup,
    bounds: &ParameterBounds,
    split_group: &str,
) -> Result<(BTreeMap<String, f64>, u32, f64), String> {
    let _ = (tapeout, rollup, bounds, split_group);
    unimplemented!()
}

