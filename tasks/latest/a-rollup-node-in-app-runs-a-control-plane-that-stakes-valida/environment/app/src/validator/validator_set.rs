use crate::store::state::AppState;

pub fn in_active_set(state: &AppState, validator_id: &str, network_id: &str) -> bool {
    state.active_set.read().unwrap().contains(network_id, validator_id)
}
