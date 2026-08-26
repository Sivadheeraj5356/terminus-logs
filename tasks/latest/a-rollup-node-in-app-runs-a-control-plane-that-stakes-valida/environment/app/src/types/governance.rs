#[derive(Clone, Copy, PartialEq)]
pub enum Visibility {
    Private,
    Public,
}

impl Visibility {
    pub fn as_str(&self) -> &'static str {
        match self {
            Visibility::Private => "private",
            Visibility::Public => "public",
        }
    }

    pub fn parse(text: &str) -> Option<Visibility> {
        match text {
            "private" => Some(Visibility::Private),
            "public" => Some(Visibility::Public),
            _ => None,
        }
    }
}

#[derive(Clone)]
pub struct Referendum {
    pub id: String,
    pub network_id: String,
    pub owner_id: String,
    pub title: String,
    pub visibility: Visibility,
    pub created_at: u64,
}

#[derive(Clone)]
pub struct BallotGrant {
    pub referendum_id: String,
    pub subject_account_id: String,
    pub granted_by: String,
    pub may_delegate: bool,
    pub created_at: u64,
}

#[derive(Clone)]
pub struct Delegation {
    pub referendum_id: String,
    pub subject_account_id: String,
    pub delegated_by: String,
    pub created_at: u64,
}

#[derive(Clone)]
pub struct GovVote {
    pub referendum_id: String,
    pub account_id: String,
    pub choice: String,
    pub cast_at: u64,
}
