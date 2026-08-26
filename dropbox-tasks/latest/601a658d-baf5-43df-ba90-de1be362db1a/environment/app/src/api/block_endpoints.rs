use super::{block_summary, block_view, events};
use crate::auth::context::AuthContext;
use crate::authz::access_control;
use crate::authz::role_registry::Permission;
use crate::consensus::block_service;
use crate::endorsement::roster;
use crate::json::{value, Json};
use crate::server::request::Request;
use crate::server::response::Response;
use crate::store::state::AppState;
use crate::types::block::Block;
use crate::types::errors::ApiError;

fn load_block(state: &AppState, id: &str) -> Result<Block, ApiError> {
    state
        .blocks
        .read()
        .unwrap()
        .get_clone(id)
        .ok_or_else(ApiError::not_found)
}

pub fn create(state: &AppState, ctx: &AuthContext, request: &Request) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::BlockCreate)?;
    let body = request
        .json()
        .map_err(|_| ApiError::bad_request("request body must be valid json"))?;
    let proposer_validator_id = body
        .string_field("proposer_validator_id")
        .ok_or_else(|| ApiError::bad_request("proposer_validator_id is required"))?;
    let parent_hash = body.string_field("parent_hash").unwrap_or_else(|| "genesis".to_string());
    let height = match body.get("height") {
        Some(Json::Num(n)) if *n >= 0.0 => *n as u64,
        _ => return Err(ApiError::bad_request("height must be a non-negative number")),
    };
    let payload = body.string_field("payload").unwrap_or_default();
    let committee_ids: Vec<String> = match body.get("committee").and_then(|v| v.as_array()) {
        Some(items) => items
            .iter()
            .filter_map(|item| item.as_str().map(|s| s.to_string()))
            .collect(),
        None => return Err(ApiError::bad_request("committee must be an array of validator ids")),
    };

    let block = block_service::create(
        state,
        ctx,
        &proposer_validator_id,
        &parent_hash,
        height,
        &payload,
        &committee_ids,
    )?;

    let mut detail = Json::obj();
    detail.set("parent_hash", value::s(&block.parent_hash));
    detail.set("height", value::n(height as i64));
    detail.set("committee_size", value::n(block.committee.len() as i64));
    events::record(state, ctx, "block.create", &block.id, "ok", detail);

    Ok(Response::json(201, block_view::detail(state, &block)))
}

pub fn list(state: &AppState, ctx: &AuthContext) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::BlockView)?;
    let blocks = state.blocks.read().unwrap().list_by_network(&ctx.network_id);
    let items: Vec<Json> = blocks.iter().map(block_summary::summary).collect();
    let mut out = Json::obj();
    out.set("blocks", Json::Arr(items));
    Ok(Response::json(200, out))
}

pub fn get(state: &AppState, ctx: &AuthContext, id: &str) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::BlockView)?;
    let block = load_block(state, id)?;
    if block.network_id != ctx.network_id {
        return Err(ApiError::not_found());
    }
    Ok(Response::json(200, block_view::detail(state, &block)))
}

pub fn endorse(state: &AppState, ctx: &AuthContext, id: &str, request: &Request) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::BlockEndorse)?;
    let block = load_block(state, id)?;
    if block.network_id != ctx.network_id {
        return Err(ApiError::not_found());
    }
    let body = request
        .json()
        .map_err(|_| ApiError::bad_request("request body must be valid json"))?;
    let validator_id = body
        .string_field("validator_id")
        .ok_or_else(|| ApiError::bad_request("validator_id is required"))?;

    block_service::record_endorsement(state, ctx, &block, &validator_id)?;
    events::record(state, ctx, "block.endorse", &block.id, "ok", Json::obj());

    let updated = load_block(state, id)?;
    Ok(Response::json(201, block_view::detail(state, &updated)))
}

pub fn list_endorsements(state: &AppState, ctx: &AuthContext, id: &str) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::BlockView)?;
    let block = load_block(state, id)?;
    if block.network_id != ctx.network_id {
        return Err(ApiError::not_found());
    }
    let records: Vec<Json> = roster::collect(&block).iter().map(|v| value::s(v)).collect();
    let mut out = Json::obj();
    out.set("endorsements", Json::Arr(records));
    out.set("endorser_count", value::n(roster::distinct(&block).len() as i64));
    Ok(Response::json(200, out))
}
