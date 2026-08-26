#[derive(Clone)]
pub struct PolicyConfig {
    pub audit_path: String,
    pub max_request_bytes: usize,
    pub min_stake: u64,
    pub finality_depth: u64,
}

impl PolicyConfig {
    pub fn default_config() -> PolicyConfig {
        PolicyConfig {
            audit_path: "/app/audit.log".to_string(),
            max_request_bytes: 65536,
            min_stake: 1,
            finality_depth: 12,
        }
    }
}
