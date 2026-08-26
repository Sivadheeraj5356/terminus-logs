pub mod account_endpoints;
pub mod admin_endpoints;
pub mod delegation_view;
pub mod events;
pub mod extract;
pub mod monitoring_endpoints;
pub mod block_endpoints;
pub mod block_summary;
pub mod block_view;
pub mod deposit_summary;
pub mod deposit_view;
pub mod relayer_endpoints;
pub mod referendum_endpoints;
pub mod referendum_summary;
pub mod referendum_view;
pub mod validator_endpoints;
pub mod validator_summary;
pub mod validator_view;

use crate::monitoring::health;
use crate::server::request::Request;
use crate::server::response::Response;
use crate::store::state::AppState;
use crate::types::errors::ApiError;

pub fn handle(state: &AppState, request: Request) -> Response {
    match dispatch(state, &request) {
        Ok(response) => response,
        Err(err) => err.to_response(),
    }
}

fn dispatch(state: &AppState, request: &Request) -> Result<Response, ApiError> {
    let method = request.method.as_str();
    let segs = request.segments();

    if request.body.len() > state.config.max_request_bytes {
        return Err(ApiError::new(413, "request_too_large", "request body is too large"));
    }

    if method == "GET" && (segs == ["v1", "health"] || segs == ["health"]) {
        return Ok(Response::json(200, health::health()));
    }
    if method == "POST" && segs == ["v1", "auth", "token"] {
        return account_endpoints::login(state, request);
    }

    if method == "GET" && segs == ["v1", "account"] {
        let ctx = extract::authenticate(state, request)?;
        return account_endpoints::get_account(state, &ctx);
    }

    if segs == ["v1", "validators"] {
        let ctx = extract::authenticate(state, request)?;
        return match method {
            "POST" => validator_endpoints::create(state, &ctx, request),
            "GET" => validator_endpoints::list(state, &ctx),
            _ => Err(method_not_allowed()),
        };
    }
    if segs.len() == 3 && segs[0] == "v1" && segs[1] == "validators" {
        let ctx = extract::authenticate(state, request)?;
        return match method {
            "GET" => validator_endpoints::get(state, &ctx, segs[2]),
            _ => Err(method_not_allowed()),
        };
    }
    if method == "POST" && segs.len() == 4 && segs[0] == "v1" && segs[1] == "validators" {
        let ctx = extract::authenticate(state, request)?;
        return match segs[3] {
            "activate" => validator_endpoints::activate(state, &ctx, segs[2]),
            "slash" => validator_endpoints::slash(state, &ctx, segs[2]),
            _ => Err(ApiError::not_found()),
        };
    }

    if segs == ["v1", "blocks"] {
        let ctx = extract::authenticate(state, request)?;
        return match method {
            "POST" => block_endpoints::create(state, &ctx, request),
            "GET" => block_endpoints::list(state, &ctx),
            _ => Err(method_not_allowed()),
        };
    }
    if segs.len() == 3 && segs[0] == "v1" && segs[1] == "blocks" {
        let ctx = extract::authenticate(state, request)?;
        return match method {
            "GET" => block_endpoints::get(state, &ctx, segs[2]),
            _ => Err(method_not_allowed()),
        };
    }
    if segs.len() == 4 && segs[0] == "v1" && segs[1] == "blocks" && segs[3] == "endorsements" {
        let ctx = extract::authenticate(state, request)?;
        return match method {
            "POST" => block_endpoints::endorse(state, &ctx, segs[2], request),
            "GET" => block_endpoints::list_endorsements(state, &ctx, segs[2]),
            _ => Err(method_not_allowed()),
        };
    }

    if segs == ["v1", "relayer", "deposits"] {
        let ctx = extract::authenticate(state, request)?;
        return match method {
            "POST" => relayer_endpoints::ingest(state, &ctx, request),
            "GET" => relayer_endpoints::list(state, &ctx),
            _ => Err(method_not_allowed()),
        };
    }
    if method == "GET" && segs.len() == 4 && segs[0] == "v1" && segs[1] == "relayer" && segs[2] == "deposits" {
        let ctx = extract::authenticate(state, request)?;
        return relayer_endpoints::get(state, &ctx, segs[3]);
    }
    if method == "POST" && segs == ["v1", "relayer", "reconcile"] {
        let ctx = extract::authenticate(state, request)?;
        return relayer_endpoints::reconcile(state, &ctx, request);
    }
    if method == "GET" && segs == ["v1", "relayer", "status"] {
        let ctx = extract::authenticate(state, request)?;
        return relayer_endpoints::status(state, &ctx);
    }

    if segs == ["v1", "referenda"] {
        let ctx = extract::authenticate(state, request)?;
        return match method {
            "POST" => referendum_endpoints::create(state, &ctx, request),
            "GET" => referendum_endpoints::list(state, &ctx),
            _ => Err(method_not_allowed()),
        };
    }
    if segs.len() == 3 && segs[0] == "v1" && segs[1] == "referenda" {
        let ctx = extract::authenticate(state, request)?;
        return match method {
            "GET" => referendum_endpoints::get(state, &ctx, segs[2]),
            _ => Err(method_not_allowed()),
        };
    }
    if segs.len() == 4 && segs[0] == "v1" && segs[1] == "referenda" && segs[3] == "grants" {
        let ctx = extract::authenticate(state, request)?;
        return match method {
            "POST" => referendum_endpoints::create_grant(state, &ctx, segs[2], request),
            "GET" => referendum_endpoints::list_grants(state, &ctx, segs[2]),
            _ => Err(method_not_allowed()),
        };
    }
    if segs.len() == 5 && segs[0] == "v1" && segs[1] == "referenda" && segs[3] == "grants" {
        let ctx = extract::authenticate(state, request)?;
        return match method {
            "DELETE" => referendum_endpoints::revoke_grant(state, &ctx, segs[2], segs[4]),
            _ => Err(method_not_allowed()),
        };
    }
    if segs.len() == 4 && segs[0] == "v1" && segs[1] == "referenda" && segs[3] == "delegations" {
        let ctx = extract::authenticate(state, request)?;
        return match method {
            "POST" => referendum_endpoints::create_delegation(state, &ctx, segs[2], request),
            "GET" => referendum_endpoints::list_delegations(state, &ctx, segs[2]),
            _ => Err(method_not_allowed()),
        };
    }
    if segs.len() == 4 && segs[0] == "v1" && segs[1] == "referenda" && segs[3] == "votes" {
        let ctx = extract::authenticate(state, request)?;
        return match method {
            "POST" => referendum_endpoints::cast_vote(state, &ctx, segs[2], request),
            "GET" => referendum_endpoints::list_votes(state, &ctx, segs[2]),
            _ => Err(method_not_allowed()),
        };
    }

    if method == "GET" && segs == ["v1", "monitoring", "stats"] {
        let ctx = extract::authenticate(state, request)?;
        return monitoring_endpoints::get_stats(state, &ctx);
    }

    if method == "POST"
        && segs.len() == 5
        && segs[0] == "v1"
        && segs[1] == "admin"
        && segs[2] == "accounts"
        && segs[4] == "suspend"
    {
        let ctx = extract::authenticate(state, request)?;
        return admin_endpoints::suspend_account(state, &ctx, segs[3]);
    }
    if method == "GET" && segs == ["v1", "admin", "audit"] {
        let ctx = extract::authenticate(state, request)?;
        return admin_endpoints::audit_log(state, &ctx, request);
    }

    Err(ApiError::not_found())
}

fn method_not_allowed() -> ApiError {
    ApiError::new(405, "method_not_allowed", "method not allowed")
}
