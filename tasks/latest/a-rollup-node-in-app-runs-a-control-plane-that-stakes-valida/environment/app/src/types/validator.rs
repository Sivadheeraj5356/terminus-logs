#[derive(Clone, Copy, PartialEq)]
pub enum ValidatorStatus {
    Registered,
    Active,
    Slashed,
}

impl ValidatorStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            ValidatorStatus::Registered => "registered",
            ValidatorStatus::Active => "active",
            ValidatorStatus::Slashed => "slashed",
        }
    }
}

#[derive(Clone)]
pub struct Validator {
    pub id: String,
    pub network_id: String,
    pub owner_id: String,
    pub name: String,
    pub stake: u64,
    pub effective_power: u64,
    pub status: ValidatorStatus,
    pub attested: bool,
    pub attestation: String,
    pub signing_key: String,
    pub session_credential: String,
    pub created_at: u64,
}
