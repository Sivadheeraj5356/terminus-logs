use crate::audit::audit_event::AuditEvent;
use crate::auth::context::AuthContext;
use crate::json::Json;
use crate::store::state::AppState;
use crate::types::clock;

pub fn record(
    state: &AppState,
    ctx: &AuthContext,
    operation: &str,
    target: &str,
    result: &str,
    detail: Json,
) {
    state.audit.record(AuditEvent {
        timestamp: clock::now_secs(),
        identity: ctx.account_id.clone(),
        client_addr: ctx.client_addr.clone(),
        operation: operation.to_string(),
        target: target.to_string(),
        result: result.to_string(),
        detail,
    });
}
