use crate::auth::context::AuthContext;
use crate::governance::vote_policy;
use crate::store::state::AppState;
use crate::types::errors::ApiError;
use crate::types::governance::Referendum;

pub fn screen(state: &AppState, ctx: &AuthContext, referendum: &Referendum) -> Result<(), ApiError> {
    vote_policy::authorize(state, ctx, referendum)
}
