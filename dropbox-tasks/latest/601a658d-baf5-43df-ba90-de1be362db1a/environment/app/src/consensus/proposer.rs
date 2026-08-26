use crate::store::state::AppState;
use crate::types::errors::ApiError;

pub fn ensure_eligible_proposer(
    state: &AppState,
    validator_id: &str,
    network_id: &str,
) -> Result<(), ApiError> {
    if state.active_set.read().unwrap().contains(network_id, validator_id) {
        Ok(())
    } else {
        Err(ApiError::unprocessable(
            "proposer_inactive",
            "proposer is not an active validator",
        ))
    }
}
