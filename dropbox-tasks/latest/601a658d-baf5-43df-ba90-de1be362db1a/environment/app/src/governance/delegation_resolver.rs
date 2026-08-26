use crate::store::state::AppState;
use crate::types::governance::Referendum;

pub fn holds_delegated(state: &AppState, account_id: &str, referendum: &Referendum) -> bool {
    let delegation = state
        .gov_delegations
        .read()
        .unwrap()
        .find(&referendum.id, account_id);
    delegation.is_some()
}
