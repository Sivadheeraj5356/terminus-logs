use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Lane {
    pub lane_id: String,
    pub source_chain: Vec<String>,
    pub receiver_chain: Vec<String>,
    pub metadata_edges: Vec<[String; 2]>,
    pub candidate_parents: Vec<String>,
    pub interrupted: bool,
    pub retry_overwrite: bool,
    pub content_match: bool,
    pub wrap_epoch: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReloadSeed {
    pub lane_id: String,
    #[serde(default)]
    pub source_chain: Option<Vec<String>>,
    #[serde(default)]
    pub receiver_chain: Option<Vec<String>>,
    #[serde(default)]
    pub metadata_edges: Option<Vec<[String; 2]>>,
    #[serde(default)]
    pub candidate_parents: Option<Vec<String>>,
    #[serde(default)]
    pub interrupted: Option<bool>,
    #[serde(default)]
    pub retry_overwrite: Option<bool>,
    #[serde(default)]
    pub content_match: Option<bool>,
    #[serde(default)]
    pub wrap_epoch: Option<u32>,
}

impl Lane {
    pub fn source_tail(&self) -> String {
        self.source_chain
            .last()
            .cloned()
            .unwrap_or_default()
    }

    pub fn chunk_anchor(&self) -> String {
        self.receiver_chain
            .last()
            .cloned()
            .unwrap_or_default()
    }

    pub fn interrupted_anchor(&self) -> String {
        let idx = self.receiver_chain.len().saturating_sub(2);
        self.receiver_chain
            .get(idx)
            .cloned()
            .unwrap_or_default()
    }

    pub fn apply_reload(&mut self, seed: &ReloadSeed) {
        if let Some(v) = &seed.source_chain {
            self.source_chain = v.clone();
        }
        if let Some(v) = &seed.receiver_chain {
            self.receiver_chain = v.clone();
        }
        if let Some(v) = &seed.metadata_edges {
            self.metadata_edges = v.clone();
        }
        if let Some(v) = &seed.candidate_parents {
            self.candidate_parents = v.clone();
        }
        if let Some(v) = seed.interrupted {
            self.interrupted = v;
        }
        if let Some(v) = seed.retry_overwrite {
            self.retry_overwrite = v;
        }
        if let Some(v) = seed.content_match {
            self.content_match = v;
        }
        if let Some(v) = seed.wrap_epoch {
            self.wrap_epoch = v;
        }
    }
}
