use crate::auth::context::AuthContext;
use crate::authz::role_registry::{self, Permission};
use crate::governance::{delegation_resolver, referendum_directory};
use crate::store::state::AppState;
use crate::types::errors::ApiError;
use crate::types::governance::{Referendum, Visibility};

pub fn authorize(state: &AppState, ctx: &AuthContext, referendum: &Referendum) -> Result<(), ApiError> {
    if referendum.network_id != ctx.network_id {
        return Err(ApiError::forbidden());
    }
    if referendum.owner_id == ctx.account_id {
        return Ok(());
    }
    if referendum_directory::holds_direct(state, &ctx.account_id, &referendum.id) {
        return Ok(());
    }
    if delegation_resolver::holds_delegated(state, &ctx.account_id, referendum) {
        return Ok(());
    }
    if referendum.visibility == Visibility::Public
        && role_registry::permits(ctx.role, Permission::GovVoteBroad)
    {
        return Ok(());
    }
    Err(ApiError::forbidden())
}
