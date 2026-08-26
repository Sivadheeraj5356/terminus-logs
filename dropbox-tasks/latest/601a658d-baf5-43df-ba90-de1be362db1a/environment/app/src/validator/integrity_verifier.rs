use super::canonical;
use crate::crypto::signature;
use crate::types::errors::ApiError;
use crate::types::validator::Validator;

pub fn verify_integrity(validator: &Validator, key: &str) -> Result<(), ApiError> {
    if validator.attestation.is_empty() {
        return Ok(());
    }
    let message = canonical::identity(validator);
    if signature::verify(key, &message, "hs256", &validator.attestation) {
        Ok(())
    } else {
        Err(ApiError::unprocessable(
            "validator_untrusted",
            "validator attestation did not verify",
        ))
    }
}
