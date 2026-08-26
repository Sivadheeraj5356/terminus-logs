use crate::types::governance::Delegation;

pub struct GovDelegationStore {
    delegations: Vec<Delegation>,
}

impl GovDelegationStore {
    pub fn new() -> GovDelegationStore {
        GovDelegationStore {
            delegations: Vec::new(),
        }
    }

    pub fn insert(&mut self, delegation: Delegation) {
        self.delegations.retain(|d| {
            !(d.referendum_id == delegation.referendum_id
                && d.subject_account_id == delegation.subject_account_id)
        });
        self.delegations.push(delegation);
    }

    pub fn find(&self, referendum_id: &str, subject_account_id: &str) -> Option<Delegation> {
        self.delegations
            .iter()
            .find(|d| d.referendum_id == referendum_id && d.subject_account_id == subject_account_id)
            .cloned()
    }

    pub fn list_by_referendum(&self, referendum_id: &str) -> Vec<Delegation> {
        self.delegations
            .iter()
            .filter(|d| d.referendum_id == referendum_id)
            .cloned()
            .collect()
    }
}
