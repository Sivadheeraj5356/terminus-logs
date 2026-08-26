use super::{deposit_summary, deposit_view, events};
use crate::auth::context::AuthContext;
use crate::authz::access_control;
use crate::authz::role_registry::Permission;
use crate::json::{value, Json};
use crate::relayer::{deposit_service, reconciler};
use crate::server::request::Request;
use crate::server::response::Response;
use crate::store::state::AppState;
use crate::types::deposit::Deposit;
use crate::types::errors::ApiError;

fn load_deposit(state: &AppState, id: &str) -> Result<Deposit, ApiError> {
    state
        .deposits
        .read()
        .unwrap()
        .get_clone(id)
        .ok_or_else(ApiError::not_found)
}

fn parse_u64(body: &Json, field: &str) -> Result<u64, ApiError> {
    match body.get(field) {
        Some(Json::Num(n)) if *n >= 0.0 && n.fract() == 0.0 => Ok(*n as u64),
        _ => Err(ApiError::bad_request(&format!("{} must be a non-negative integer", field))),
    }
}

pub fn ingest(state: &AppState, ctx: &AuthContext, request: &Request) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::RelayerManage)?;
    let body = request
        .json()
        .map_err(|_| ApiError::bad_request("request body must be valid json"))?;
    let l1_height = parse_u64(&body, "l1_height")?;
    let amount = parse_u64(&body, "amount")?;
    let recipient = body
        .string_field("recipient_account_id")
        .ok_or_else(|| ApiError::bad_request("recipient_account_id is required"))?;

    let deposit = deposit_service::ingest(state, ctx, l1_height, &recipient, amount)?;

    let mut detail = Json::obj();
    detail.set("l1_height", value::n(l1_height as i64));
    detail.set("recipient_account_id", value::s(&recipient));
    detail.set("amount", value::n(amount as i64));
    events::record(state, ctx, "relayer.ingest", &deposit.id, "ok", detail);

    Ok(Response::json(201, deposit_view::detail(&deposit)))
}

pub fn list(state: &AppState, ctx: &AuthContext) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::RelayerView)?;
    let deposits = state.deposits.read().unwrap().list_by_network(&ctx.network_id);
    let items: Vec<Json> = deposits.iter().map(deposit_summary::summary).collect();
    let mut out = Json::obj();
    out.set("deposits", Json::Arr(items));
    Ok(Response::json(200, out))
}

pub fn get(state: &AppState, ctx: &AuthContext, id: &str) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::RelayerView)?;
    let deposit = load_deposit(state, id)?;
    if deposit.network_id != ctx.network_id {
        return Err(ApiError::not_found());
    }
    Ok(Response::json(200, deposit_view::detail(&deposit)))
}

pub fn reconcile(state: &AppState, ctx: &AuthContext, request: &Request) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::RelayerManage)?;
    let body = request
        .json()
        .map_err(|_| ApiError::bad_request("request body must be valid json"))?;
    let l1_tip = parse_u64(&body, "l1_tip")?;

    let outcome = reconciler::reconcile(state, ctx, l1_tip);

    let applied: Vec<Json> = outcome
        .applied
        .iter()
        .map(|a| {
            Json::from_pairs(vec![
                ("id", value::s(&a.id)),
                ("l1_height", value::n(a.l1_height as i64)),
                ("confirmations", value::n(a.confirmations as i64)),
            ])
        })
        .collect();

    let mut detail = Json::obj();
    detail.set("l1_tip", value::n(outcome.l1_tip as i64));
    detail.set("applied_count", value::n(outcome.applied.len() as i64));
    events::record(state, ctx, "relayer.reconcile", &ctx.network_id, "ok", detail);

    let mut out = Json::obj();
    out.set("network_id", value::s(&ctx.network_id));
    out.set("l1_tip", value::n(outcome.l1_tip as i64));
    out.set("finality_depth", value::n(outcome.finality_depth as i64));
    out.set("applied_count", value::n(outcome.applied.len() as i64));
    out.set("applied", Json::Arr(applied));
    Ok(Response::json(200, out))
}

pub fn status(state: &AppState, ctx: &AuthContext) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::RelayerView)?;
    let deposits = state.deposits.read().unwrap();
    let total = deposits.count_by_network(&ctx.network_id);
    let applied = deposits.applied_count_by_network(&ctx.network_id);
    let tip = deposits.l1_tip(&ctx.network_id);

    let mut out = Json::obj();
    out.set("network_id", value::s(&ctx.network_id));
    out.set("l1_tip", value::n(tip as i64));
    out.set("finality_depth", value::n(state.config.finality_depth as i64));
    out.set("deposit_count", value::n(total as i64));
    out.set("applied_deposit_count", value::n(applied as i64));
    out.set("pending_deposit_count", value::n((total - applied) as i64));
    Ok(Response::json(200, out))
}
