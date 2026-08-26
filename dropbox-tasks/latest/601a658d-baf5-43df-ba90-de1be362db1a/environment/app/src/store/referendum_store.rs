use crate::types::governance::Referendum;
use std::collections::HashMap;

pub struct ReferendumStore {
    by_id: HashMap<String, Referendum>,
}

impl ReferendumStore {
    pub fn new() -> ReferendumStore {
        ReferendumStore {
            by_id: HashMap::new(),
        }
    }

    pub fn insert(&mut self, referendum: Referendum) {
        self.by_id.insert(referendum.id.clone(), referendum);
    }

    pub fn get_clone(&self, id: &str) -> Option<Referendum> {
        self.by_id.get(id).cloned()
    }

    pub fn list_by_network(&self, network_id: &str) -> Vec<Referendum> {
        let mut out: Vec<Referendum> = self
            .by_id
            .values()
            .filter(|r| r.network_id == network_id)
            .cloned()
            .collect();
        out.sort_by(|a, b| a.created_at.cmp(&b.created_at));
        out
    }

    pub fn count_by_network(&self, network_id: &str) -> usize {
        self.by_id.values().filter(|r| r.network_id == network_id).count()
    }
}
