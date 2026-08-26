use super::{delegation_view, events, referendum_summary, referendum_view};
use crate::auth::context::AuthContext;
use crate::authz::access_control;
use crate::authz::role_registry::{self, Permission};
use crate::json::{value, Json};
use crate::middleware::access_guard;
use crate::server::request::Request;
use crate::server::response::Response;
use crate::store::state::AppState;
use crate::types::clock;
use crate::types::errors::ApiError;
use crate::types::governance::{BallotGrant, Delegation, GovVote, Referendum, Visibility};
use crate::types::ids;

fn load_referendum(state: &AppState, id: &str) -> Result<Referendum, ApiError> {
    state
        .referenda
        .read()
        .unwrap()
        .get_clone(id)
        .ok_or_else(ApiError::not_found)
}

fn owns_or_manages(ctx: &AuthContext, referendum: &Referendum) -> Result<(), ApiError> {
    if referendum.network_id != ctx.network_id {
        return Err(ApiError::not_found());
    }
    if referendum.owner_id == ctx.account_id
        || role_registry::permits(ctx.role, Permission::ReferendumManage)
    {
        Ok(())
    } else {
        Err(ApiError::forbidden())
    }
}

pub fn create(state: &AppState, ctx: &AuthContext, request: &Request) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::ReferendumCreate)?;
    let body = request
        .json()
        .map_err(|_| ApiError::bad_request("request body must be valid json"))?;
    let title = body
        .string_field("title")
        .ok_or_else(|| ApiError::bad_request("title is required"))?;
    if title.trim().is_empty() {
        return Err(ApiError::bad_request("title must not be empty"));
    }
    let visibility = match body.string_field("visibility") {
        Some(text) => Visibility::parse(&text)
            .ok_or_else(|| ApiError::bad_request("visibility must be private or public"))?,
        None => Visibility::Private,
    };

    let referendum = Referendum {
        id: ids::new_id("refm"),
        network_id: ctx.network_id.clone(),
        owner_id: ctx.account_id.clone(),
        title: title.clone(),
        visibility,
        created_at: clock::now_secs(),
    };
    state.referenda.write().unwrap().insert(referendum.clone());
    events::record(state, ctx, "referendum.create", &referendum.id, "ok", Json::obj());
    Ok(Response::json(201, referendum_view::detail(&referendum)))
}

pub fn list(state: &AppState, ctx: &AuthContext) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::ReferendumView)?;
    let referenda = state.referenda.read().unwrap().list_by_network(&ctx.network_id);
    let items: Vec<Json> = referenda.iter().map(referendum_summary::summary).collect();
    let mut out = Json::obj();
    out.set("referenda", Json::Arr(items));
    Ok(Response::json(200, out))
}

pub fn get(state: &AppState, ctx: &AuthContext, id: &str) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::ReferendumView)?;
    let referendum = load_referendum(state, id)?;
    if referendum.network_id != ctx.network_id {
        return Err(ApiError::not_found());
    }
    Ok(Response::json(200, referendum_view::detail(&referendum)))
}

pub fn create_grant(
    state: &AppState,
    ctx: &AuthContext,
    id: &str,
    request: &Request,
) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::BallotGrantManage)?;
    let referendum = load_referendum(state, id)?;
    owns_or_manages(ctx, &referendum)?;
    let body = request
        .json()
        .map_err(|_| ApiError::bad_request("request body must be valid json"))?;
    let subject = body
        .string_field("subject_account_id")
        .ok_or_else(|| ApiError::bad_request("subject_account_id is required"))?;
    let may_delegate = match body.get("may_delegate") {
        Some(Json::Bool(b)) => *b,
        None => false,
        _ => return Err(ApiError::bad_request("may_delegate must be a boolean")),
    };
    state.ballot_grants.write().unwrap().insert(BallotGrant {
        referendum_id: referendum.id.clone(),
        subject_account_id: subject.clone(),
        granted_by: ctx.account_id.clone(),
        may_delegate,
        created_at: clock::now_secs(),
    });
    events::record(state, ctx, "referendum.grant", &referendum.id, "ok", Json::obj());
    let mut out = Json::obj();
    out.set("referendum_id", value::s(&referendum.id));
    out.set("subject_account_id", value::s(&subject));
    out.set("may_delegate", value::b(may_delegate));
    Ok(Response::json(201, out))
}

pub fn list_grants(state: &AppState, ctx: &AuthContext, id: &str) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::ReferendumView)?;
    let referendum = load_referendum(state, id)?;
    owns_or_manages(ctx, &referendum)?;
    let grants = state.ballot_grants.read().unwrap().list_by_referendum(&referendum.id);
    let items: Vec<Json> = grants
        .iter()
        .map(|g| {
            Json::from_pairs(vec![
                ("subject_account_id", value::s(&g.subject_account_id)),
                ("may_delegate", value::b(g.may_delegate)),
            ])
        })
        .collect();
    let mut out = Json::obj();
    out.set("grants", Json::Arr(items));
    Ok(Response::json(200, out))
}

pub fn revoke_grant(
    state: &AppState,
    ctx: &AuthContext,
    id: &str,
    subject: &str,
) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::BallotGrantManage)?;
    let referendum = load_referendum(state, id)?;
    owns_or_manages(ctx, &referendum)?;
    let removed = state.ballot_grants.write().unwrap().remove(&referendum.id, subject);
    if !removed {
        return Err(ApiError::not_found());
    }
    events::record(state, ctx, "referendum.revoke", &referendum.id, "ok", Json::obj());
    let mut out = Json::obj();
    out.set("referendum_id", value::s(&referendum.id));
    out.set("subject_account_id", value::s(subject));
    out.set("revoked", value::b(true));
    Ok(Response::json(200, out))
}

pub fn create_delegation(
    state: &AppState,
    ctx: &AuthContext,
    id: &str,
    request: &Request,
) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::GovVoteCast)?;
    let referendum = load_referendum(state, id)?;
    if referendum.network_id != ctx.network_id {
        return Err(ApiError::not_found());
    }
    let grant = state.ballot_grants.read().unwrap().find(&referendum.id, &ctx.account_id);
    let may_delegate = grant.map(|g| g.may_delegate).unwrap_or(false);
    if !may_delegate {
        return Err(ApiError::forbidden());
    }
    let body = request
        .json()
        .map_err(|_| ApiError::bad_request("request body must be valid json"))?;
    let subject = body
        .string_field("subject_account_id")
        .ok_or_else(|| ApiError::bad_request("subject_account_id is required"))?;
    let subject_account = state.accounts.read().unwrap().get_clone(&subject);
    match subject_account {
        Some(account) if account.network_id == ctx.network_id => {}
        _ => return Err(ApiError::unprocessable("unknown_subject", "subject account is not in this network")),
    }
    state.gov_delegations.write().unwrap().insert(Delegation {
        referendum_id: referendum.id.clone(),
        subject_account_id: subject.clone(),
        delegated_by: ctx.account_id.clone(),
        created_at: clock::now_secs(),
    });
    events::record(state, ctx, "referendum.delegate", &referendum.id, "ok", Json::obj());
    let mut out = Json::obj();
    out.set("referendum_id", value::s(&referendum.id));
    out.set("subject_account_id", value::s(&subject));
    Ok(Response::json(201, out))
}

pub fn list_delegations(state: &AppState, ctx: &AuthContext, id: &str) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::ReferendumView)?;
    let referendum = load_referendum(state, id)?;
    if referendum.network_id != ctx.network_id {
        return Err(ApiError::not_found());
    }
    let delegations = state.gov_delegations.read().unwrap().list_by_referendum(&referendum.id);
    let items: Vec<Json> = delegations
        .iter()
        .map(|d| delegation_view::detail(state, &referendum, d))
        .collect();
    let mut out = Json::obj();
    out.set("delegations", Json::Arr(items));
    Ok(Response::json(200, out))
}

pub fn list_votes(state: &AppState, ctx: &AuthContext, id: &str) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::ReferendumView)?;
    let referendum = load_referendum(state, id)?;
    owns_or_manages(ctx, &referendum)?;
    let votes = state.gov_votes.read().unwrap().list_by_referendum(&referendum.id);
    let items: Vec<Json> = votes
        .iter()
        .map(|v| {
            Json::from_pairs(vec![
                ("account_id", value::s(&v.account_id)),
                ("choice", value::s(&v.choice)),
            ])
        })
        .collect();
    let mut out = Json::obj();
    out.set("votes", Json::Arr(items));
    Ok(Response::json(200, out))
}

pub fn cast_vote(
    state: &AppState,
    ctx: &AuthContext,
    id: &str,
    request: &Request,
) -> Result<Response, ApiError> {
    access_control::require(ctx, Permission::GovVoteCast)?;
    let referendum = load_referendum(state, id)?;
    access_guard::screen(state, ctx, &referendum)?;
    let body = request
        .json()
        .map_err(|_| ApiError::bad_request("request body must be valid json"))?;
    let choice = body.string_field("choice").unwrap_or_else(|| "aye".to_string());
    state.gov_votes.write().unwrap().insert(GovVote {
        referendum_id: referendum.id.clone(),
        account_id: ctx.account_id.clone(),
        choice: choice.clone(),
        cast_at: clock::now_secs(),
    });
    events::record(state, ctx, "referendum.vote", &referendum.id, "ok", Json::obj());
    let mut out = Json::obj();
    out.set("referendum_id", value::s(&referendum.id));
    out.set("choice", value::s(&choice));
    out.set("recorded", value::b(true));
    Ok(Response::json(201, out))
}
