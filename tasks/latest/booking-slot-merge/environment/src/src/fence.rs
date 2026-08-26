use std::collections::HashMap;

use crate::parser::{self, Slot};

/// Keep only rows whose epoch equals the per-resource minimum seen in `slots`.
pub fn survivors(slots: &[Slot]) -> Vec<Slot> {
    let mut min_by_resource: HashMap<String, u64> = HashMap::new();
    for s in slots {
        let key = parser::canonical_resource(&s.resource);
        let e = min_by_resource.entry(key).or_insert(u64::MAX);
        if s.epoch < *e {
            *e = s.epoch;
        }
    }
    slots
        .iter()
        .filter(|s| {
            let key = parser::canonical_resource(&s.resource);
            s.epoch == *min_by_resource.get(&key).unwrap_or(&0)
        })
        .cloned()
        .collect()
}
