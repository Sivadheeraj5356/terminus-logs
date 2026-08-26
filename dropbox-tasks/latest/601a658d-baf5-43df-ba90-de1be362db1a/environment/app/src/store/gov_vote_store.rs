use crate::types::governance::GovVote;

pub struct GovVoteStore {
    votes: Vec<GovVote>,
}

impl GovVoteStore {
    pub fn new() -> GovVoteStore {
        GovVoteStore { votes: Vec::new() }
    }

    pub fn insert(&mut self, vote: GovVote) {
        self.votes.retain(|v| {
            !(v.referendum_id == vote.referendum_id && v.account_id == vote.account_id)
        });
        self.votes.push(vote);
    }

    pub fn list_by_referendum(&self, referendum_id: &str) -> Vec<GovVote> {
        self.votes
            .iter()
            .filter(|v| v.referendum_id == referendum_id)
            .cloned()
            .collect()
    }
}
