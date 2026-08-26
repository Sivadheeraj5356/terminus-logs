use manifest::{Geometry, Leaf, StateA};

#[derive(Debug)]
pub struct FoldError(pub String);

impl std::fmt::Display for FoldError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

include!(concat!(env!("CARGO_MANIFEST_DIR"), "/../rxb/body.rs"));
