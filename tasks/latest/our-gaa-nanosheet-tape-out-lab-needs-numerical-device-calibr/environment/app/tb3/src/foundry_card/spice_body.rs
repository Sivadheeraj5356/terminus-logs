use std::collections::BTreeMap;

use crate::{FittedParams, CalibrationTapeout};

pub struct SpiceCard {
    pub header: String,
    pub body: String,
}

/// Write the SPICE model card to disk.
pub fn write_spice(
    path: &std::path::Path,
    tapeout: &CalibrationTapeout,
    fitted: &[FittedParams],
) -> Result<(), String> {
    let _ = (path, tapeout, fitted);
    unimplemented!()
}

/// Render the SPICE model card text.
pub fn render_spice(tapeout: &CalibrationTapeout, fitted: &[FittedParams]) -> SpiceCard {
    let _ = (tapeout, fitted);
    unimplemented!()
}

pub fn param_lookup(fitted: &[FittedParams], split_group: &str) -> BTreeMap<String, f64> {
    fitted
        .iter()
        .find(|g| g.split_group == split_group)
        .map(|g| g.values.clone())
        .unwrap_or_default()
}
