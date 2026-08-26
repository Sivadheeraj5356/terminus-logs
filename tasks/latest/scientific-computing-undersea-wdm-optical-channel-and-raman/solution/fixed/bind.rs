/// Select next-hop channel.
pub fn knit_u(prev_lambda: i32, at_regen: bool, free: &[i32]) -> Option<i32> {
    if free.is_empty() {
        return None;
    }
    let mut ordered = free.to_vec();
    ordered.sort_unstable();
    let lowest = ordered.first().copied();
    if prev_lambda < 0 || at_regen {
        return lowest;
    }
    if !ordered.iter().any(|&c| c == prev_lambda) {
        return None;
    }
    Some(prev_lambda)
}
