use crate::store::state::AppState;

pub fn effective_power(state: &AppState, validator_id: &str) -> u64 {
    state
        .validators
        .read()
        .unwrap()
        .get_clone(validator_id)
        .map(|v| v.effective_power)
        .unwrap_or(0)
}
