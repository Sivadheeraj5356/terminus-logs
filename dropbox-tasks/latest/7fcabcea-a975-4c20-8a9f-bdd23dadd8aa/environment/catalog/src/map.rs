use manifest::{Entry, Registry, SpanKey};

#[derive(Debug)]
pub struct MapError(pub String);

impl std::fmt::Display for MapError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

include!(concat!(env!("CARGO_MANIFEST_DIR"), "/../rxa/body.rs"));
