use crate::auth::context::AuthContext;
use crate::auth::credential_store;
use crate::crypto::{rng, tokens};
use crate::json::{value, Json};
use crate::server::request::Request;
use crate::server::response::Response;
use crate::store::state::AppState;
use crate::types::account::ApiToken;
use crate::types::clock;
use crate::types::errors::ApiError;

pub fn login(state: &AppState, request: &Request) -> Result<Response, ApiError> {
    let body = request
        .json()
        .map_err(|_| ApiError::bad_request("request body must be valid json"))?;
    let username = body
        .string_field("username")
        .ok_or_else(|| ApiError::bad_request("username is required"))?;
    let password = body
        .string_field("password")
        .ok_or_else(|| ApiError::bad_request("password is required"))?;

    let account = {
        let accounts = state.accounts.read().unwrap();
        credential_store::login(&accounts, &username, &password)?
    };

    let raw = rng::token_hex(24);
    let fingerprint = tokens::fingerprint(&raw);
    let expires_at = clock::now_secs() + 3600;
    state.tokens.write().unwrap().insert(ApiToken {
        account_id: account.id.clone(),
        fingerprint,
        expires_at,
        revoked: false,
    });

    let mut out = Json::obj();
    out.set("token", value::s(&raw));
    out.set("account_id", value::s(&account.id));
    out.set("network_id", value::s(&account.network_id));
    out.set("role", value::s(account.role.as_str()));
    out.set("expires_at", value::n(expires_at as i64));
    Ok(Response::json(200, out))
}

pub fn get_account(state: &AppState, ctx: &AuthContext) -> Result<Response, ApiError> {
    let account = state
        .accounts
        .read()
        .unwrap()
        .get_clone(&ctx.account_id)
        .ok_or_else(ApiError::not_found)?;
    let network_name = state
        .networks
        .read()
        .unwrap()
        .get_clone(&account.network_id)
        .map(|n| n.name)
        .unwrap_or_default();
    let mut out = Json::obj();
    out.set("id", value::s(&account.id));
    out.set("username", value::s(&account.username));
    out.set("network_id", value::s(&account.network_id));
    out.set("network_name", value::s(&network_name));
    out.set("role", value::s(account.role.as_str()));
    out.set("status", value::s(account.status.as_str()));
    out.set("l2_balance", value::n(account.l2_balance as i64));
    Ok(Response::json(200, out))
}
