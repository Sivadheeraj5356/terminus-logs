use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Serialize, Eq, PartialEq)]
pub struct RawDoc {
    pub doc_id: String,
    pub tokens: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize, Eq, PartialEq)]
pub struct StagedDoc {
    pub doc_id: String,
    pub token_ids: Vec<usize>,
}

#[derive(Clone, Debug, Deserialize, Serialize, Eq, PartialEq)]
pub struct CorpusStaging {
    pub schema: String,
    pub vocab: Vec<String>,
    pub docs: Vec<StagedDoc>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct CountStaging {
    pub schema: String,
    pub k: usize,
    pub alpha: f64,
    pub beta: f64,
    pub seed: u64,
    pub sweeps: usize,
    pub burn_in: usize,
    pub retained_sweeps: usize,
    pub vocab: Vec<String>,
    pub doc_ids: Vec<String>,
    pub assignments: Vec<Vec<usize>>,
    pub n_dk: Vec<Vec<u64>>,
    pub n_kw: Vec<Vec<u64>>,
    pub n_k: Vec<u64>,
    pub theta_sum: Vec<Vec<f64>>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct TopTerm {
    pub token: String,
    pub probability: f64,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct TopicRollup {
    pub topic: usize,
    pub top_terms: Vec<TopTerm>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct DocTheta {
    pub doc_id: String,
    pub theta: Vec<f64>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct Rollup {
    pub schema: String,
    pub retained_sweeps: usize,
    pub topics: Vec<TopicRollup>,
    pub documents: Vec<DocTheta>,
    pub snapshot_checksum: String,
}
