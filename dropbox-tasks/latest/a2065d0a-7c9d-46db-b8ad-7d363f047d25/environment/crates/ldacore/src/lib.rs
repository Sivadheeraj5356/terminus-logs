pub mod config;
pub mod corpus;
pub mod decoy;
pub mod engine;
pub mod ingest;
pub mod ledger;
pub mod model;
pub mod publication;
pub mod ranking;
pub mod retention;
pub mod rng;
pub mod sampler;
pub mod snapshot;
pub mod vocab;

use anyhow::{Context, Result};
use std::fs;
use std::path::Path;

pub fn read_json<T: serde::de::DeserializeOwned>(path: &Path) -> Result<T> {
    let bytes = fs::read(path).with_context(|| format!("read {}", path.display()))?;
    Ok(serde_json::from_slice(&bytes)?)
}

pub fn stable_bytes<T: serde::Serialize>(value: &T) -> Result<Vec<u8>> {
    let mut bytes = serde_json::to_vec(value)?;
    bytes.push(b'\n');
    Ok(bytes)
}

pub fn write_if_changed(path: &Path, bytes: &[u8]) -> Result<()> {
    if fs::read(path).ok().as_deref() == Some(bytes) {
        return Ok(());
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let tmp = path.with_extension("tmp");
    fs::write(&tmp, bytes)?;
    fs::rename(tmp, path)?;
    Ok(())
}
