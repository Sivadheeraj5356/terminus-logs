//! Bounded parameter recovery — incomplete starter.

use crate::error::{SolverError, SolverResult};

pub fn solve_fits(_data: &crate::data::SolverData) -> SolverResult<()> {
    Err(SolverError::new(
        "bounded one- and two-parameter inversion is not implemented",
    ))
}
