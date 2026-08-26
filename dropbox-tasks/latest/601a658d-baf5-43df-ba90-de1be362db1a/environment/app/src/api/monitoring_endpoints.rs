use crate::auth::context::AuthContext;
use crate::monitoring::{access, stats};
use crate::server::response::Response;
use crate::store::state::AppState;
use crate::types::errors::ApiError;

pub fn get_stats(state: &AppState, ctx: &AuthContext) -> Result<Response, ApiError> {
    access::require_view(ctx)?;
    Ok(Response::json(200, stats::network_stats(state, &ctx.network_id)))
}
