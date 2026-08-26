use std::collections::HashMap;
use std::collections::HashSet;

pub struct ActiveSetStore {
    by_network: HashMap<String, HashSet<String>>,
}

impl ActiveSetStore {
    pub fn new() -> ActiveSetStore {
        ActiveSetStore {
            by_network: HashMap::new(),
        }
    }

    pub fn add(&mut self, network_id: &str, validator_id: &str) {
        self.by_network
            .entry(network_id.to_string())
            .or_insert_with(HashSet::new)
            .insert(validator_id.to_string());
    }

    pub fn remove(&mut self, network_id: &str, validator_id: &str) {
        if let Some(members) = self.by_network.get_mut(network_id) {
            members.remove(validator_id);
        }
    }

    pub fn contains(&self, network_id: &str, validator_id: &str) -> bool {
        self.by_network
            .get(network_id)
            .map(|members| members.contains(validator_id))
            .unwrap_or(false)
    }

    pub fn count(&self, network_id: &str) -> usize {
        self.by_network
            .get(network_id)
            .map(|members| members.len())
            .unwrap_or(0)
    }
}
