use std::collections::BTreeMap;

use crate::types::ScopeRecord;

pub fn consolidate_records(records: Vec<ScopeRecord>) -> Vec<ScopeRecord> {
    let mut best: BTreeMap<u32, ScopeRecord> = BTreeMap::new();
    for rec in records {
        match best.get(&rec.scope_id) {
            None => {
                best.insert(rec.scope_id, rec);
            }
            Some(cur) => {
                if rec.rotate_gen > cur.rotate_gen {
                    best.insert(rec.scope_id, rec);
                }
            }
        }
    }
    best.into_values().collect()
}
