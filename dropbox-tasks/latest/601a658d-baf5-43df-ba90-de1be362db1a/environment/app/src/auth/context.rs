use crate::types::account::Role;

#[derive(Clone)]
pub struct AuthContext {
    pub account_id: String,
    pub network_id: String,
    pub role: Role,
    pub client_addr: String,
}
