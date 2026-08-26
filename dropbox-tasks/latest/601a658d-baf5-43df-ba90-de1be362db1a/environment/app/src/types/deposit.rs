#[derive(Clone, PartialEq)]
pub enum DepositStatus {
    Pending,
    Applied,
}

impl DepositStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            DepositStatus::Pending => "pending",
            DepositStatus::Applied => "applied",
        }
    }
}

#[derive(Clone)]
pub struct Deposit {
    pub id: String,
    pub network_id: String,
    pub owner_id: String,
    pub l1_height: u64,
    pub recipient_account_id: String,
    pub amount: u64,
    pub status: DepositStatus,
    pub applied_at_tip: Option<u64>,
    pub created_at: u64,
}
