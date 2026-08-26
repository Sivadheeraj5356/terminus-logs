use std::os::unix::io::RawFd;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum LingerError {
    #[error("poll: {0}")]
    Poll(#[from] std::io::Error),
}

pub struct LingerPlane;

impl LingerPlane {
    pub fn new() -> Self {
        Self
    }

    /// Baseline tick: no hangup detection wired yet.
    pub fn op_a(&mut self, _fds: &[(u32, RawFd)]) -> Vec<u32> {
        vec![]
    }

    pub fn reconcile_b(&mut self, _dead: &[u32]) {}
}

impl Default for LingerPlane {
    fn default() -> Self {
        Self::new()
    }
}
