use std::path::Path;

#[derive(Debug, Clone, serde::Deserialize)]
pub struct Policy {
    pub policy_id: String,
    pub min_depth_m: i64,
    pub max_depth_m: i64,
    pub allowed_obs_types: Vec<String>,
}

pub fn load_policy(path: &Path) -> Result<Policy, String> {
    let raw = std::fs::read_to_string(path).map_err(|_| "POLICY_READ_ERROR".to_string())?;
    serde_json::from_str(&raw).map_err(|_| "POLICY_READ_ERROR".to_string())
}
