/// Merged span length in milliseconds for a resource's max-epoch rows.
pub fn resource_span(min_start: u64, max_end: u64, empty: bool) -> u64 {
    if empty {
        0
    } else {
        max_end.saturating_sub(min_start).saturating_add(1)
    }
}
