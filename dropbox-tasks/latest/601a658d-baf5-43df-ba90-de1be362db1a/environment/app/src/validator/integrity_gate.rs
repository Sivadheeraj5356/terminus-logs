use super::integrity_verifier;
use crate::store::state::AppState;
use crate::types::errors::ApiError;
use crate::types::validator::Validator;

pub fn ensure_attested(state: &AppState, validator: &Validator) -> Result<(), ApiError> {
    integrity_verifier::verify_integrity(validator, state.secrets.attest_key())
}
