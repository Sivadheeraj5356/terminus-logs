use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct InputRecord {
    pub group_id: String,
    pub timestamp: u64,
    pub values: Vec<f64>,
    pub source: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChainState {
    pub id: String,
    pub history: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ArtifactRecord {
    pub group_id: String,
    pub key: String,
    pub history: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ProbeVec {
    pub id: usize,
    pub vec: Vec<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Output {
    pub probe_id: usize,
    pub value: f64,
    pub key: String,
}
