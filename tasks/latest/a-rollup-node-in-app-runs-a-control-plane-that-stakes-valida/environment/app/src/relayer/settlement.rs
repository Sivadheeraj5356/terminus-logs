use crate::relayer::finality_gate;
use crate::store::state::AppState;

pub fn settle(state: &AppState, network_id: &str, l1_tip: u64, finality_depth: u64) -> Vec<String> {
    let pending = state.deposits.read().unwrap().pending_by_network(network_id);
    let mut applied = Vec::new();
    for deposit in &pending {
        if finality_gate::is_final(deposit, l1_tip, finality_depth) {
            state.deposits.write().unwrap().mark_applied(&deposit.id, l1_tip);
            applied.push(deposit.id.clone());
        }
    }
    applied
}
