//! Finite-volume thermal transport — incomplete in the candidate starter.

use crate::error::{SolverError, SolverResult};

pub fn solve_cases(_data: &crate::data::SolverData) -> SolverResult<()> {
    Err(SolverError::new(
        "thermal finite-volume stepping and spin-up are not implemented",
    ))
}
