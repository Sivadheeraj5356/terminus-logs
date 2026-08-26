use super::account_status;
use crate::crypto::hashing;
use crate::store::account_store::AccountStore;
use crate::types::account::Account;
use crate::types::errors::ApiError;

pub fn login(accounts: &AccountStore, username: &str, password: &str) -> Result<Account, ApiError> {
    let account = match accounts.by_username(username) {
        Some(account) => account,
        None => {
            return Err(ApiError::new(
                404,
                "unknown_account",
                "no account matches that username",
            ))
        }
    };
    if !hashing::verify_password(password, &account.password_salt, &account.password_hash) {
        return Err(ApiError::unauthorized());
    }
    account_status::ensure_usable(&account)?;
    Ok(account)
}
