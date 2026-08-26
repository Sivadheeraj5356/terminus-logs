use crate::auth::context::AuthContext;
use crate::authz::role_registry::{self, Permission};
use crate::types::errors::ApiError;
use crate::types::validator::Validator;

pub fn authorize(ctx: &AuthContext, validator: &Validator) -> Result<(), ApiError> {
    if validator.owner_id == ctx.account_id {
        return Ok(());
    }
    if role_registry::permits(ctx.role, Permission::ValidatorView) {
        return Ok(());
    }
    Err(ApiError::forbidden())
}
