use crate::store::state::AppState;
use crate::types::governance::Referendum;

pub fn holds(state: &AppState, account_id: &str, referendum: &Referendum) -> bool {
    if referendum.owner_id == account_id {
        return true;
    }
    state
        .ballot_grants
        .read()
        .unwrap()
        .find(&referendum.id, account_id)
        .is_some()
}
