#[derive(Clone, Copy, PartialEq)]
pub enum Role {
    Participant,
    Operator,
    Admin,
}

impl Role {
    pub fn as_str(&self) -> &'static str {
        match self {
            Role::Participant => "participant",
            Role::Operator => "operator",
            Role::Admin => "admin",
        }
    }
}

#[derive(Clone, Copy, PartialEq)]
pub enum AccountStatus {
    Active,
    Suspended,
}

impl AccountStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            AccountStatus::Active => "active",
            AccountStatus::Suspended => "suspended",
        }
    }
}

#[derive(Clone)]
pub struct Account {
    pub id: String,
    pub network_id: String,
    pub username: String,
    pub password_salt: String,
    pub password_hash: String,
    pub role: Role,
    pub status: AccountStatus,
    pub l2_balance: u64,
}

#[derive(Clone)]
pub struct ApiToken {
    pub account_id: String,
    pub fingerprint: String,
    pub expires_at: u64,
    pub revoked: bool,
}
