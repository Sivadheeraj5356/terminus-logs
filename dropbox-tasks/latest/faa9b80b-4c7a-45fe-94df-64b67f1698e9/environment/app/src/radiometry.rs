//! Planck radiometry and brightness temperature — incomplete starter.

use crate::error::{SolverError, SolverResult};

pub fn band_radiance(_temperature_k: f64) -> SolverResult<f64> {
    Err(SolverError::new(
        "band-integrated Planck radiometry is not implemented",
    ))
}

pub fn brightness_temperature(_radiance: f64) -> SolverResult<f64> {
    Err(SolverError::new(
        "brightness-temperature inversion is not implemented",
    ))
}
