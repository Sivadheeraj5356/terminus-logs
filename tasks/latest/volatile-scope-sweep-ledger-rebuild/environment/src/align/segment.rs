use std::collections::BTreeMap;

use crate::types::ScopeRecord;

pub fn segment_by_time(records: &[ScopeRecord], width_ms: u64) -> BTreeMap<u64, Vec<ScopeRecord>> {
    let w = width_ms.max(1);
    let mut buckets: BTreeMap<u64, Vec<ScopeRecord>> = BTreeMap::new();
    for rec in records {
        let start = (rec.ts_ms / w) * w + 1;
        buckets.entry(start).or_default().push(rec.clone());
    }
    buckets
}
