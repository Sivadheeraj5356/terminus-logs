use super::{events, validator_summary, validator_view};
use crate::auth::context::AuthContext;
use crate::authz::access_control;
use crate::authz::role_registry::Permission;
use crate::crypto::tokens;
use crate::json::{value, Json};
use crate::server::request::Request;
use crate::server::response::Response;
use crate::stake::{registration, slashing};
use crate::store::state::AppState;
use crate::types::account::Role;
use crate::types::errors::ApiError;
use crate::types::validator::{Validator, ValidatorStatus};
use crate::validator::{integrity_gate, provisioning, validator_access, validator_status};

fn load_validator(state: &AppState, id: &str) -> Result<Validator, ApiError> {
    state
        .validators
        .read()
        .unwrap()
        .get_clone(id)
        .ok_or_else(ApiError::not_found)
}

fn manageable(ctx: &AuthContext, validator: &Validator) -> Result<(), ApiError> {
    if validator.network_id != ctx.network_id {
        return Err(ApiError::not_found());
    }
    if validator.owner_id == ctx.account_id || ctx.role != Role::Participant {
        Ok(())
    } else {
        Err(ApiError::forbidden())
    }
}

pub fn create(state: &AppState, ctx: &AuthContext, request: &Request) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::ValidatorRegister)?;
    let body = request
        .json()
        .map_err(|_| ApiError::bad_request("request body must be valid json"))?;
    let name = body
        .string_field("name")
        .ok_or_else(|| ApiError::bad_request("name is required"))?;
    if name.trim().is_empty() {
        return Err(ApiError::bad_request("name must not be empty"));
    }
    let stake = match body.get("stake") {
        Some(Json::Num(n)) if *n >= 1.0 => *n as u64,
        None => state.config.min_stake,
        _ => return Err(ApiError::bad_request("stake must be a positive number")),
    };
    registration::validate_stake(stake, state.config.min_stake)?;
    let attested = match body.get("attested") {
        Some(Json::Bool(b)) => *b,
        None => true,
        _ => return Err(ApiError::bad_request("attested must be a boolean")),
    };

    let validator = provisioning::build(ctx, &name, stake, attested, state.secrets.attest_key());
    state.validators.write().unwrap().insert(validator.clone());

    let mut detail = Json::obj();
    detail.set("name", value::s(&validator.name));
    detail.set("stake", value::n(validator.stake as i64));
    detail.set("signing_key", value::s(&validator.signing_key));
    events::record(state, ctx, "validator.register", &validator.id, "ok", detail);

    Ok(Response::json(201, validator_view::detail(&validator)))
}

pub fn list(state: &AppState, ctx: &AuthContext) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::ValidatorView)?;
    let validators = state.validators.read().unwrap().list_by_network(&ctx.network_id);
    let items: Vec<Json> = validators.iter().map(validator_summary::summary).collect();
    let mut out = Json::obj();
    out.set("validators", Json::Arr(items));
    Ok(Response::json(200, out))
}

pub fn get(state: &AppState, ctx: &AuthContext, id: &str) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::ValidatorView)?;
    let validator = load_validator(state, id)?;
    validator_access::authorize(ctx, &validator)?;
    Ok(Response::json(200, validator_view::detail(&validator)))
}

pub fn activate(state: &AppState, ctx: &AuthContext, id: &str) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::ValidatorManage)?;
    let validator = load_validator(state, id)?;
    manageable(ctx, &validator)?;
    validator_status::ensure_manageable(&validator)?;
    integrity_gate::ensure_attested(state, &validator)?;

    let credential = tokens::mint_secret();
    {
        let mut validators = state.validators.write().unwrap();
        validators.set_status(id, ValidatorStatus::Active);
        validators.set_session_credential(id, &credential);
    }
    state.active_set.write().unwrap().add(&ctx.network_id, id);

    let mut detail = Json::obj();
    detail.set("validator_id", value::s(id));
    detail.set("session_credential", value::s(&credential));
    events::record(state, ctx, "validator.activate", id, "ok", detail);

    let updated = load_validator(state, id)?;
    let mut out = Json::obj();
    out.set("validator", validator_view::detail(&updated));
    out.set("session_credential", value::s(&credential));
    Ok(Response::json(200, out))
}

pub fn slash(state: &AppState, ctx: &AuthContext, id: &str) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::ValidatorSlash)?;
    let validator = load_validator(state, id)?;
    if validator.network_id != ctx.network_id {
        return Err(ApiError::not_found());
    }
    slashing::slash(state, id, &ctx.network_id);
    events::record(state, ctx, "validator.slash", id, "ok", Json::obj());
    let updated = load_validator(state, id)?;
    Ok(Response::json(200, validator_view::detail(&updated)))
}
