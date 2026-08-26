use crate::governance::seat_authority;
use crate::store::state::AppState;
use crate::types::governance::{Delegation, Referendum};

pub fn is_active(state: &AppState, referendum: &Referendum, delegation: &Delegation) -> bool {
    seat_authority::holds(state, &delegation.delegated_by, referendum)
}
