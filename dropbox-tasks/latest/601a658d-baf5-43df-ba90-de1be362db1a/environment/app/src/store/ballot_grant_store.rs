use crate::types::governance::BallotGrant;

pub struct BallotGrantStore {
    grants: Vec<BallotGrant>,
}

impl BallotGrantStore {
    pub fn new() -> BallotGrantStore {
        BallotGrantStore { grants: Vec::new() }
    }

    pub fn insert(&mut self, grant: BallotGrant) {
        self.grants.retain(|g| {
            !(g.referendum_id == grant.referendum_id
                && g.subject_account_id == grant.subject_account_id)
        });
        self.grants.push(grant);
    }

    pub fn remove(&mut self, referendum_id: &str, subject_account_id: &str) -> bool {
        let before = self.grants.len();
        self.grants.retain(|g| {
            !(g.referendum_id == referendum_id && g.subject_account_id == subject_account_id)
        });
        self.grants.len() != before
    }

    pub fn find(&self, referendum_id: &str, subject_account_id: &str) -> Option<BallotGrant> {
        self.grants
            .iter()
            .find(|g| g.referendum_id == referendum_id && g.subject_account_id == subject_account_id)
            .cloned()
    }

    pub fn list_by_referendum(&self, referendum_id: &str) -> Vec<BallotGrant> {
        self.grants
            .iter()
            .filter(|g| g.referendum_id == referendum_id)
            .cloned()
            .collect()
    }
}
