use crate::fence;
use crate::parser::{self, Slot};

/// Rows at each resource's minimum epoch only (survivor selection).
pub fn max_epoch_rows(slots: &[Slot]) -> Vec<Slot> {
    fence::survivors(slots)
}

pub fn duplicate_slot_id(slots: &[Slot]) -> bool {
    let mut seen = std::collections::HashMap::<u64, usize>::new();
    for s in slots {
        *seen.entry(s.slot_id).or_insert(0) += 1;
    }
    seen.values().any(|&c| c > 1)
}

/// Epoch regression within each file independently.
pub fn has_epoch_regression(dir: &str) -> Result<bool, String> {
    let paths = parser::list_slot_files(dir)?;
    if paths.is_empty() {
        return Err("no slots".to_string());
    }
    for path in &paths {
        let mut max_seen: std::collections::HashMap<String, u64> = std::collections::HashMap::new();
        for row in parser::read_file(std::path::Path::new(path))? {
            let key = parser::canonical_resource(&row.resource);
            if let Some(&m) = max_seen.get(&key) {
                if row.epoch < m {
                    return Ok(true);
                }
                if row.epoch > m {
                    max_seen.insert(key, row.epoch);
                }
            } else {
                max_seen.insert(key, row.epoch);
            }
        }
    }
    Ok(false)
}
