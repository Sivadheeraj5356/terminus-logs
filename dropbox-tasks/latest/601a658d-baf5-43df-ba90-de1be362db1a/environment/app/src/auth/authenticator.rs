use super::account_status;
use super::context::AuthContext;
use super::token_verifier;
use crate::server::request::Request;
use crate::store::state::AppState;
use crate::types::errors::ApiError;

pub fn authenticate(state: &AppState, request: &Request) -> Result<AuthContext, ApiError> {
    let header = request
        .header("authorization")
        .ok_or_else(ApiError::unauthorized)?;
    let presented = header
        .strip_prefix("Bearer ")
        .or_else(|| header.strip_prefix("bearer "))
        .ok_or_else(ApiError::unauthorized)?
        .trim();

    let verified = {
        let tokens = state.tokens.read().unwrap();
        token_verifier::verify(&tokens, presented).ok_or_else(ApiError::unauthorized)?
    };

    let account = {
        let accounts = state.accounts.read().unwrap();
        accounts
            .get_clone(&verified.account_id)
            .ok_or_else(ApiError::unauthorized)?
    };
    account_status::ensure_usable(&account)?;

    let context = AuthContext {
        account_id: account.id.clone(),
        network_id: account.network_id.clone(),
        role: account.role,
        client_addr: request.peer.clone(),
    };
    Ok(context)
}
