//! Nonlinear residual helpers for backward-Euler steps — incomplete starter.

use crate::error::{SolverError, SolverResult};

pub fn solve_nonlinear_step(_residual_tol: f64) -> SolverResult<()> {
    Err(SolverError::new(
        "nonlinear temperature residual solver is not implemented",
    ))
}
