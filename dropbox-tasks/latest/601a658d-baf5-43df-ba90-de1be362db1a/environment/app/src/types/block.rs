#[derive(Clone)]
pub struct CommitteeMember {
    pub validator_id: String,
    pub weight: u64,
}

#[derive(Clone)]
pub struct Block {
    pub id: String,
    pub network_id: String,
    pub parent_hash: String,
    pub proposer_account_id: String,
    pub proposer_validator_id: String,
    pub height: u64,
    pub payload_hash: String,
    pub committee: Vec<CommitteeMember>,
    pub total_power: u64,
    pub endorsements: Vec<String>,
    pub created_at: u64,
}
