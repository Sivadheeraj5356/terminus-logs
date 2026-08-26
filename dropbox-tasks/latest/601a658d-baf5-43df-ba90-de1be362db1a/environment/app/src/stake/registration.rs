use crate::types::errors::ApiError;

pub fn validate_stake(stake: u64, min_stake: u64) -> Result<(), ApiError> {
    if stake < min_stake {
        return Err(ApiError::bad_request("stake is below the configured minimum"));
    }
    Ok(())
}
