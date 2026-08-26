/// Admission counter lines used by console status emission.
pub fn tally_line(accepted: u32, rejected: u32) -> String {
    let ratio = if accepted == 0 {
        0u32
    } else {
        (rejected.saturating_mul(100)) / accepted.max(1)
    };
    format!(
        "accepted={} refused={} refuse_pct={}",
        accepted, rejected, ratio
    )
}

/// Compact progress badge printed beside run records.
pub fn badge(accepted: u32) -> String {
    if accepted > 12 {
        "dense".into()
    } else if accepted > 4 {
        "steady".into()
    } else {
        "sparse".into()
    }
}
