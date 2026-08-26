use crate::store::state::AppState;
use crate::validator::validator_set;

pub fn counts(state: &AppState, validator_id: &str, network_id: &str) -> bool {
    validator_set::in_active_set(state, validator_id, network_id)
}
