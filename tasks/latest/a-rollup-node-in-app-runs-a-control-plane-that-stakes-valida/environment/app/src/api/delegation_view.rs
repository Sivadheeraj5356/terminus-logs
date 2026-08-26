use crate::governance::delegation_status;
use crate::json::{value, Json};
use crate::store::state::AppState;
use crate::types::governance::{Delegation, Referendum};

pub fn detail(state: &AppState, referendum: &Referendum, delegation: &Delegation) -> Json {
    let active = delegation_status::is_active(state, referendum, delegation);
    Json::from_pairs(vec![
        ("referendum_id", value::s(&delegation.referendum_id)),
        ("subject_account_id", value::s(&delegation.subject_account_id)),
        ("delegated_by", value::s(&delegation.delegated_by)),
        ("active", value::b(active)),
    ])
}
