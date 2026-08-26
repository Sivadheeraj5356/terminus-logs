use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct LogicalId(pub String);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ObjectKind {
    Set,
    Chain,
    Rule,
}

impl LogicalId {
    pub fn new(raw: impl Into<String>) -> Self {
        Self(raw.into())
    }
}
