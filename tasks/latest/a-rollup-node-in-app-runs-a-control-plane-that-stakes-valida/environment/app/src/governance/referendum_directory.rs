use crate::store::state::AppState;

pub fn holds_direct(state: &AppState, account_id: &str, referendum_id: &str) -> bool {
    state
        .ballot_grants
        .read()
        .unwrap()
        .find(referendum_id, account_id)
        .is_some()
}
