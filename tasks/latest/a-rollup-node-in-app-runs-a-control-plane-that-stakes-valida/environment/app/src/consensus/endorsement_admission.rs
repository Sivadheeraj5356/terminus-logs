use crate::store::state::AppState;
use crate::types::errors::ApiError;

pub fn ensure_can_endorse(
    state: &AppState,
    validator_id: &str,
    network_id: &str,
) -> Result<(), ApiError> {
    if state.active_set.read().unwrap().contains(network_id, validator_id) {
        Ok(())
    } else {
        Err(ApiError::conflict(
            "validator_inactive",
            "validator is not in the active set and cannot endorse",
        ))
    }
}
