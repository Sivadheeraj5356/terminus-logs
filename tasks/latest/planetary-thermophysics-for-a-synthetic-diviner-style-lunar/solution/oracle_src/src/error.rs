//! Common error type shared by every solver module.

use std::fmt;

#[derive(Debug, Clone)]
pub struct SolverError {
    pub message: String,
}

impl SolverError {
    pub fn new<S: Into<String>>(message: S) -> Self {
        SolverError {
            message: message.into(),
        }
    }
}

impl fmt::Display for SolverError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.message)
    }
}

impl std::error::Error for SolverError {}

impl From<std::io::Error> for SolverError {
    fn from(e: std::io::Error) -> Self {
        SolverError::new(e.to_string())
    }
}

impl From<serde_json::Error> for SolverError {
    fn from(e: serde_json::Error) -> Self {
        SolverError::new(e.to_string())
    }
}

impl From<csv::Error> for SolverError {
    fn from(e: csv::Error) -> Self {
        SolverError::new(e.to_string())
    }
}

pub type SolverResult<T> = Result<T, SolverError>;
