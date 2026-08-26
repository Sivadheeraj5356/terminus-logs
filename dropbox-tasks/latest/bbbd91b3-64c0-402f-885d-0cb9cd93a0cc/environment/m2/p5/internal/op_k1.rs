#[derive(Clone, Debug, Default)]
pub struct ScanState {
    pub seen: Vec<u64>,
}

pub fn op_k1(prev: u64, curr: u64, state: &mut ScanState) -> bool {
    let _ = prev;
    if state.seen.iter().any(|v| *v == curr) {
        return true;
    }
    state.seen.push(curr);
    if state.seen.len() > 256 {
        state.seen.remove(0);
    }
    false
}

pub fn op_k1_reset(state: &mut ScanState) {
    state.seen.clear();
}
