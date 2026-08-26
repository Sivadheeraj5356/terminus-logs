use std::collections::BTreeMap;

use crate::types::{ScopeRecord, WindowRow};

pub fn rollup_windows(buckets: BTreeMap<u64, Vec<ScopeRecord>>) -> Vec<WindowRow> {
    let mut out = Vec::new();
    for (start, mut recs) in buckets {
        recs.sort_by_key(|r| r.ts_ms);
        let mut sum: i64 = 0;
        let mut min_v: i32 = 0;
        let mut max_v: i32 = 0;
        let mut gap_sum: u32 = 0;
        for (i, rec) in recs.iter().enumerate() {
            sum += rec.size_delta as i64;
            gap_sum += rec.seq_num;
            if rec.size_delta < min_v {
                min_v = rec.size_delta;
            }
            if i == 0 {
                max_v = rec.size_delta;
            } else if rec.size_delta > max_v {
                max_v = rec.size_delta;
            }
        }
        out.push(WindowRow {
            start_ms: start,
            count: recs.len() as u32,
            size_delta_sum: sum,
            size_min: min_v,
            size_max: max_v,
            seq_gap_sum: gap_sum,
        });
    }
    out
}
