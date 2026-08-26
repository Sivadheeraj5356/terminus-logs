use anyhow::{Context, Result};
use serde::Deserialize;
use std::fs;

#[derive(Debug, Clone, Deserialize)]
pub struct AttnProfile {
    pub br_cap: u32,
    pub bc_cap: u32,
    pub head_dim: u32,
    pub block_tokens: u32,
    pub compact_threshold: f64,
    pub n_heads: u32,
    /// XOR salt for spinal seal trailer (tip XOR spine_salt).
    #[serde(default)]
    pub spine_salt: u64,
}

pub fn load_profile(path: &str) -> Result<AttnProfile> {
    let raw = fs::read_to_string(path).with_context(|| format!("read profile {path}"))?;
    Ok(serde_json::from_str(&raw)?)
}
