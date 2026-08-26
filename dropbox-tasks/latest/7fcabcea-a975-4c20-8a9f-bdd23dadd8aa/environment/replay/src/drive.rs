use manifest::{BookE, FrameD, Snapshot};

#[derive(Debug)]
pub struct ReplayError(pub String);

impl std::fmt::Display for ReplayError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

include!(concat!(env!("CARGO_MANIFEST_DIR"), "/../rxd/body.rs"));
