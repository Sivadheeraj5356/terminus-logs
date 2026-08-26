use crate::types::network::Network;
use std::collections::HashMap;

pub struct NetworkStore {
    by_id: HashMap<String, Network>,
}

impl NetworkStore {
    pub fn new() -> NetworkStore {
        NetworkStore {
            by_id: HashMap::new(),
        }
    }

    pub fn insert(&mut self, network: Network) {
        self.by_id.insert(network.id.clone(), network);
    }

    pub fn get_clone(&self, id: &str) -> Option<Network> {
        self.by_id.get(id).cloned()
    }
}
