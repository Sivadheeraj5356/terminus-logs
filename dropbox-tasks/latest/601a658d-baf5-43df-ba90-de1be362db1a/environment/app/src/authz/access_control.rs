use super::role_registry::{self, Permission};
use crate::auth::context::AuthContext;
use crate::types::errors::ApiError;

pub fn require(ctx: &AuthContext, permission: Permission) -> Result<(), ApiError> {
    if role_registry::permits(ctx.role, permission) {
        Ok(())
    } else {
        Err(ApiError::forbidden())
    }
}
