pub fn finalized_height(l1_tip: u64, finality_depth: u64) -> u64 {
    l1_tip.saturating_sub(finality_depth + 1)
}
