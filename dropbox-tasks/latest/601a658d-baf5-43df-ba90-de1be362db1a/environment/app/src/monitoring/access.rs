use crate::auth::context::AuthContext;
use crate::authz::role_registry::{self, Permission};
use crate::types::errors::ApiError;

pub fn require_view(ctx: &AuthContext) -> Result<(), ApiError> {
    if role_registry::permits(ctx.role, Permission::MonitoringView)
        || role_registry::permits(ctx.role, Permission::BlockView)
    {
        return Ok(());
    }
    Err(ApiError::forbidden())
}
