use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StatusReport {
    pub schema_version: u32,
    pub ok: bool,
    pub phase: String,
    pub generation: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pending_generation: Option<u64>,
    pub managed_rules: usize,
    pub foreign_rules: usize,
    #[serde(default)]
    pub reason_codes: Vec<String>,
}

impl Default for StatusReport {
    fn default() -> Self {
        Self {
            schema_version: 1,
            ok: true,
            phase: "empty".into(),
            generation: 0,
            pending_generation: None,
            managed_rules: 0,
            foreign_rules: 0,
            reason_codes: Vec::new(),
        }
    }
}
