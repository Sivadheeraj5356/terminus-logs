use crate::auth::context::AuthContext;
use crate::relayer::{confirmations, settlement, settlement_credit};
use crate::store::state::AppState;

pub struct AppliedDeposit {
    pub id: String,
    pub l1_height: u64,
    pub confirmations: u64,
}

pub struct ReconcileOutcome {
    pub l1_tip: u64,
    pub finality_depth: u64,
    pub applied: Vec<AppliedDeposit>,
}

pub fn reconcile(state: &AppState, ctx: &AuthContext, requested_tip: u64) -> ReconcileOutcome {
    let finality_depth = state.config.finality_depth;
    let applied_ids = settlement::settle(state, &ctx.network_id, requested_tip, finality_depth);
    state.deposits.write().unwrap().observe_tip(&ctx.network_id, requested_tip);

    let mut applied = Vec::new();
    for id in &applied_ids {
        if let Some(deposit) = state.deposits.read().unwrap().get_clone(id) {
            settlement_credit::credit(state, ctx, &deposit, requested_tip);
            applied.push(AppliedDeposit {
                id: deposit.id.clone(),
                l1_height: deposit.l1_height,
                confirmations: confirmations::count(&deposit, requested_tip),
            });
        }
    }
    ReconcileOutcome {
        l1_tip: state.deposits.read().unwrap().l1_tip(&ctx.network_id),
        finality_depth,
        applied,
    }
}
