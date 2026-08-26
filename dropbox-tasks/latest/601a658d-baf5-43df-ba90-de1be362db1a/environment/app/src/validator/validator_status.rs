use crate::types::errors::ApiError;
use crate::types::validator::{Validator, ValidatorStatus};

pub fn ensure_manageable(validator: &Validator) -> Result<(), ApiError> {
    match validator.status {
        ValidatorStatus::Slashed => Err(ApiError::conflict(
            "validator_slashed",
            "validator has been slashed and cannot be reconfigured",
        )),
        _ => Ok(()),
    }
}
