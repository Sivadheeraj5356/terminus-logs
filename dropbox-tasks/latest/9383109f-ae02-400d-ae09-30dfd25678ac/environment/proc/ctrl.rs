use std::collections::HashMap;
use crate::types::{ChainState, InputRecord};
use crate::proc::ingest::op_a;
use crate::proc::tracker::reconcile_b;

pub struct StateController {
    pub chains: HashMap<String, ChainState>,
}

impl Default for StateController {
    fn default() -> Self {
        Self::new()
    }
}

impl StateController {
    pub fn new() -> Self {
        Self {
            chains: HashMap::new(),
        }
    }

    pub fn process_batch(&mut self, records: &[InputRecord]) {
        for record in records {
            let group_id = &record.group_id;
            let default_prior = ChainState {
                id: group_id.clone(),
                history: Vec::new(),
            };
            let prior = self.chains.get(group_id).unwrap_or(&default_prior);
            let mut updated = op_a(record, prior);
            if updated.history.len() > 2 {
                let start = updated.history.len() - 2;
                updated.history = updated.history[start..].to_vec();
            }
            updated = crate::proc::tracker::normalize_merge_tail(&updated);
            self.chains.insert(group_id.clone(), updated);
        }
    }

    pub fn merge_with(&mut self, other: &StateController) {
        for (group_id, other_chain) in &other.chains {
            if let Some(our_chain) = self.chains.get(group_id) {
                let merged = reconcile_b(our_chain, other_chain);
                self.chains.insert(group_id.clone(), merged);
            } else {
                self.chains.insert(group_id.clone(), other_chain.clone());
            }
        }
    }
}
