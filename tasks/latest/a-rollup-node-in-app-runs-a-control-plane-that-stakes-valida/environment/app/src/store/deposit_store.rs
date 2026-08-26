use crate::types::deposit::{Deposit, DepositStatus};
use std::collections::HashMap;

pub struct DepositStore {
    by_id: HashMap<String, Deposit>,
    l1_tip: HashMap<String, u64>,
}

impl DepositStore {
    pub fn new() -> DepositStore {
        DepositStore {
            by_id: HashMap::new(),
            l1_tip: HashMap::new(),
        }
    }

    pub fn insert(&mut self, deposit: Deposit) {
        self.by_id.insert(deposit.id.clone(), deposit);
    }

    pub fn get_clone(&self, id: &str) -> Option<Deposit> {
        self.by_id.get(id).cloned()
    }

    pub fn mark_applied(&mut self, id: &str, tip: u64) {
        if let Some(deposit) = self.by_id.get_mut(id) {
            deposit.status = DepositStatus::Applied;
            deposit.applied_at_tip = Some(tip);
        }
    }

    pub fn pending_by_network(&self, network_id: &str) -> Vec<Deposit> {
        let mut out: Vec<Deposit> = self
            .by_id
            .values()
            .filter(|d| d.network_id == network_id && d.status == DepositStatus::Pending)
            .cloned()
            .collect();
        out.sort_by(|a, b| a.l1_height.cmp(&b.l1_height));
        out
    }

    pub fn list_by_network(&self, network_id: &str) -> Vec<Deposit> {
        let mut out: Vec<Deposit> = self
            .by_id
            .values()
            .filter(|d| d.network_id == network_id)
            .cloned()
            .collect();
        out.sort_by(|a, b| a.created_at.cmp(&b.created_at));
        out
    }

    pub fn count_by_network(&self, network_id: &str) -> usize {
        self.by_id.values().filter(|d| d.network_id == network_id).count()
    }

    pub fn applied_count_by_network(&self, network_id: &str) -> usize {
        self.by_id
            .values()
            .filter(|d| d.network_id == network_id && d.status == DepositStatus::Applied)
            .count()
    }

    pub fn l1_tip(&self, network_id: &str) -> u64 {
        *self.l1_tip.get(network_id).unwrap_or(&0)
    }

    pub fn observe_tip(&mut self, network_id: &str, tip: u64) {
        let entry = self.l1_tip.entry(network_id.to_string()).or_insert(0);
        if tip > *entry {
            *entry = tip;
        }
    }
}
