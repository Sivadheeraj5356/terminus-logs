use crate::store::state::AppState;
use crate::types::errors::ApiError;

pub fn validate(
    state: &AppState,
    network_id: &str,
    l1_height: u64,
    recipient_account_id: &str,
    amount: u64,
) -> Result<(), ApiError> {
    if l1_height == 0 {
        return Err(ApiError::bad_request("l1_height must be a positive block number"));
    }
    if amount == 0 {
        return Err(ApiError::bad_request("amount must be a positive number"));
    }
    let recipient = state
        .accounts
        .read()
        .unwrap()
        .get_clone(recipient_account_id)
        .ok_or_else(|| ApiError::unprocessable("unknown_recipient", "recipient account does not exist"))?;
    if recipient.network_id != network_id {
        return Err(ApiError::unprocessable(
            "foreign_recipient",
            "recipient account belongs to another network",
        ));
    }
    Ok(())
}
