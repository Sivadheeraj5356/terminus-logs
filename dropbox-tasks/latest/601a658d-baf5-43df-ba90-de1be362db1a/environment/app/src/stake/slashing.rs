use crate::store::state::AppState;
use crate::types::validator::ValidatorStatus;

pub fn slash(state: &AppState, validator_id: &str, network_id: &str) {
    state.validators.write().unwrap().set_power(validator_id, 0);
    state
        .validators
        .write()
        .unwrap()
        .set_status(validator_id, ValidatorStatus::Slashed);
    state.active_set.write().unwrap().remove(network_id, validator_id);
}
