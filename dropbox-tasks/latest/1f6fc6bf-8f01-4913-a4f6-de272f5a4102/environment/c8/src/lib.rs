use serde::Deserialize;
use thiserror::Error;

#[derive(Debug, Clone, Deserialize)]
pub struct ShardEndpoint {
    pub id: u32,
    pub host: String,
    pub port: u16,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Policy {
    pub pool_max_per_shard: u32,
    pub descriptor_ceiling: u32,
    pub idle_close_ms: u32,
    pub populate_sleep_ms: u32,
    pub shards: Vec<ShardEndpoint>,
}

#[derive(Debug, Error)]
pub enum PolicyError {
    #[error("read policy: {0}")]
    Read(#[from] std::io::Error),
    #[error("parse policy: {0}")]
    Parse(#[from] toml::de::Error),
    #[error("unknown shard profile {0}")]
    Profile(String),
}

pub fn load(path: &str) -> Result<Policy, PolicyError> {
    let raw = std::fs::read_to_string(path)?;
    Ok(toml::from_str(&raw)?)
}

pub fn resolve_profile(policy: &Policy, profile: &str) -> Result<Vec<ShardEndpoint>, PolicyError> {
    if profile == "all" {
        return Ok(policy.shards.clone());
    }
    if profile == "primary" {
        return Ok(policy.shards.iter().take(1).cloned().collect());
    }
    Err(PolicyError::Profile(profile.to_string()))
}
