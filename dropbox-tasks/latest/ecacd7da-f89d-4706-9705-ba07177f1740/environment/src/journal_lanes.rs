use crate::journal::OpEntry;

pub fn finalize_order(mut rows: Vec<OpEntry>) -> Vec<OpEntry> {
    rows.sort_by_key(|entry| entry.seq);
    rows
}
