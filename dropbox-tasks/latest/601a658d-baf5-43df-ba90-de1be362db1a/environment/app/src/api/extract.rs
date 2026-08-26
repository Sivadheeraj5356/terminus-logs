use crate::audit::audit_event::AuditEvent;
use crate::auth::authenticator;
use crate::auth::context::AuthContext;
use crate::json::{value, Json};
use crate::server::request::Request;
use crate::store::state::AppState;
use crate::types::clock;
use crate::types::errors::ApiError;

pub fn authenticate(state: &AppState, request: &Request) -> Result<AuthContext, ApiError> {
    match authenticator::authenticate(state, request) {
        Ok(context) => Ok(context),
        Err(err) => {
            record_failure(state, request, &err);
            Err(err)
        }
    }
}

fn record_failure(state: &AppState, request: &Request, err: &ApiError) {
    let mut detail = Json::obj();
    detail.set("path", value::s(&request.path));
    detail.set("reason", value::s(&err.code));
    state.audit.record(AuditEvent {
        timestamp: clock::now_secs(),
        identity: "anonymous".to_string(),
        client_addr: request.peer.clone(),
        operation: "auth.failed".to_string(),
        target: request.path.clone(),
        result: "denied".to_string(),
        detail,
    });
}
