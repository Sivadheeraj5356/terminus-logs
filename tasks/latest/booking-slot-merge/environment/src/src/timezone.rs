/// Inclusive end timestamps are stored in venue-local epoch milliseconds.
/// Convert to an exclusive upper bound for interval geometry.
pub fn exclusive_end(inclusive_end: u64) -> u64 {
    inclusive_end.saturating_sub(1)
}
