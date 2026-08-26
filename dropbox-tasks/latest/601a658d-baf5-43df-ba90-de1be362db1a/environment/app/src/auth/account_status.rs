use crate::types::account::{Account, AccountStatus};
use crate::types::errors::ApiError;

pub fn ensure_usable(account: &Account) -> Result<(), ApiError> {
    if account.status == AccountStatus::Suspended {
        return Err(ApiError::new(403, "account_suspended", "account is not active"));
    }
    Ok(())
}
