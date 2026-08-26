use anyhow::Result;
use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct AttnProfile {
    pub br_cap: u32,
    pub bc_cap: u32,
    pub head_dim: u32,
    pub block_tokens: u32,
    pub compact_threshold: f64,
    pub n_heads: u32,
    #[serde(default)]
    pub spine_salt: u64,
}

pub fn load_profile(_path: &str) -> Result<AttnProfile> {
    unimplemented!("load_profile")
}
