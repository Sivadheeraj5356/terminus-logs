use crate::types::validator::{Validator, ValidatorStatus};
use std::collections::HashMap;

pub struct ValidatorStore {
    by_id: HashMap<String, Validator>,
}

impl ValidatorStore {
    pub fn new() -> ValidatorStore {
        ValidatorStore {
            by_id: HashMap::new(),
        }
    }

    pub fn insert(&mut self, validator: Validator) {
        self.by_id.insert(validator.id.clone(), validator);
    }

    pub fn get_clone(&self, id: &str) -> Option<Validator> {
        self.by_id.get(id).cloned()
    }

    pub fn set_status(&mut self, id: &str, status: ValidatorStatus) -> bool {
        if let Some(validator) = self.by_id.get_mut(id) {
            validator.status = status;
            true
        } else {
            false
        }
    }

    pub fn set_power(&mut self, id: &str, power: u64) -> bool {
        if let Some(validator) = self.by_id.get_mut(id) {
            validator.effective_power = power;
            true
        } else {
            false
        }
    }

    pub fn set_session_credential(&mut self, id: &str, credential: &str) -> bool {
        if let Some(validator) = self.by_id.get_mut(id) {
            validator.session_credential = credential.to_string();
            true
        } else {
            false
        }
    }

    pub fn list_by_network(&self, network_id: &str) -> Vec<Validator> {
        let mut out: Vec<Validator> = self
            .by_id
            .values()
            .filter(|v| v.network_id == network_id)
            .cloned()
            .collect();
        out.sort_by(|a, b| a.created_at.cmp(&b.created_at));
        out
    }

    pub fn count_by_network(&self, network_id: &str) -> usize {
        self.by_id.values().filter(|v| v.network_id == network_id).count()
    }
}
