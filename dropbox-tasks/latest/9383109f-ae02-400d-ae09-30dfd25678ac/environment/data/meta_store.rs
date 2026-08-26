use std::collections::HashMap;
use crate::types::ArtifactRecord;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetadataStore {
    pub records: HashMap<String, ArtifactRecord>,
}

impl Default for MetadataStore {
    fn default() -> Self {
        Self::new()
    }
}

impl MetadataStore {
    pub fn new() -> Self {
        Self {
            records: HashMap::new(),
        }
    }

    pub fn insert(&mut self, record: ArtifactRecord) {
        self.records.insert(record.group_id.clone(), record);
    }

    pub fn get(&self, group_id: &str) -> Option<&ArtifactRecord> {
        self.records.get(group_id)
    }

    pub fn get_canonical_key(&self, probe_id: usize) -> Option<String> {
        let group_id = format!("G{}", probe_id);
        self.get(&group_id).map(|r| {
            if r.history.len() > 1 {
                r.history.first().cloned().unwrap_or_else(|| r.key.clone())
            } else {
                r.key.clone()
            }
        })
    }
}
