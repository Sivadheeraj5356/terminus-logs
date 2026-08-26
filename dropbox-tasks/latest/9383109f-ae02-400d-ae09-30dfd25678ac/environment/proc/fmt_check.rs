use crate::types::InputRecord;

pub fn verify_format(records: &[InputRecord]) -> bool {
    for record in records {
        if record.group_id.is_empty() || record.values.is_empty() {
            return false;
        }
    }
    true
}
