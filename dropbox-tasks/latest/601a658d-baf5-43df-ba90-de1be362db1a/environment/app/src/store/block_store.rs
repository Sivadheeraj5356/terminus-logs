use crate::types::block::Block;
use std::collections::HashMap;

pub struct BlockStore {
    by_id: HashMap<String, Block>,
}

impl BlockStore {
    pub fn new() -> BlockStore {
        BlockStore {
            by_id: HashMap::new(),
        }
    }

    pub fn insert(&mut self, block: Block) {
        self.by_id.insert(block.id.clone(), block);
    }

    pub fn get_clone(&self, id: &str) -> Option<Block> {
        self.by_id.get(id).cloned()
    }

    pub fn add_endorsement(&mut self, id: &str, validator_id: &str) -> bool {
        if let Some(block) = self.by_id.get_mut(id) {
            block.endorsements.push(validator_id.to_string());
            true
        } else {
            false
        }
    }

    pub fn list_by_network(&self, network_id: &str) -> Vec<Block> {
        let mut out: Vec<Block> = self
            .by_id
            .values()
            .filter(|p| p.network_id == network_id)
            .cloned()
            .collect();
        out.sort_by(|a, b| a.created_at.cmp(&b.created_at));
        out
    }

    pub fn count_by_network(&self, network_id: &str) -> usize {
        self.by_id.values().filter(|p| p.network_id == network_id).count()
    }
}
