use crate::types::InputRecord;

pub fn sort_records(records: &mut [InputRecord]) {
    records.sort_by_key(|r| r.timestamp);
}
