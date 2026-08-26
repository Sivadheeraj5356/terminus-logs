use super::events;
use crate::audit::{field_scrubber, redactor};
use crate::auth::context::AuthContext;
use crate::authz::access_control;
use crate::authz::role_registry::Permission;
use crate::json::{value, Json};
use crate::server::request::Request;
use crate::server::response::Response;
use crate::store::state::AppState;
use crate::types::account::AccountStatus;
use crate::types::errors::ApiError;

pub fn suspend_account(
    state: &AppState,
    ctx: &AuthContext,
    username: &str,
) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::AccountAdmin)?;
    let account = {
        let accounts = state.accounts.read().unwrap();
        accounts.by_username(username).ok_or_else(ApiError::not_found)?
    };
    if account.network_id != ctx.network_id {
        return Err(ApiError::forbidden());
    }
    state.accounts.write().unwrap().set_status(&account.id, AccountStatus::Suspended);
    events::record(state, ctx, "account.suspend", &account.id, "ok", Json::obj());
    let mut out = Json::obj();
    out.set("username", value::s(username));
    out.set("status", value::s("suspended"));
    Ok(Response::json(200, out))
}

pub fn audit_log(state: &AppState, ctx: &AuthContext, request: &Request) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::AuditView)?;
    let limit = request
        .query_param("limit")
        .and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(50)
        .min(500);
    let records = state.audit.recent(limit);
    let items: Vec<Json> = records
        .iter()
        .map(|event| {
            let mut detail = event.detail.clone();
            field_scrubber::scrub(&mut detail);
            redactor::redact(&mut detail);
            Json::from_pairs(vec![
                ("timestamp", value::n(event.timestamp as i64)),
                ("identity", value::s(&event.identity)),
                ("client_addr", value::s(&event.client_addr)),
                ("operation", value::s(&event.operation)),
                ("target", value::s(&event.target)),
                ("result", value::s(&event.result)),
                ("detail", detail),
            ])
        })
        .collect();
    let mut out = Json::obj();
    out.set("records", Json::Arr(items));
    Ok(Response::json(200, out))
}
