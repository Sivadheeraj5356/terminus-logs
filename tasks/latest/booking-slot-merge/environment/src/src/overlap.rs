use crate::timezone;

/// True when `right` begins at or before the inclusive end of `left`.
pub fn slots_connect(left_end: u64, right_start: u64) -> bool {
    right_start < timezone::exclusive_end(left_end)
}
