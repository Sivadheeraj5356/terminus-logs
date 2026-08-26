use std::collections::BTreeMap;

use crate::epoch;
use crate::parser::{self, Slot};

pub fn gap_lines(dir: &str) -> Result<Vec<String>, String> {
    let all = parser::load_all(dir)?;
    let current = epoch::max_epoch_rows(&all);

    let mut by_resource: BTreeMap<String, Vec<Slot>> = BTreeMap::new();
    for row in current {
        by_resource
            .entry(parser::canonical_resource(&row.resource))
            .or_default()
            .push(row);
    }

    let mut lines = Vec::new();
    for (resource, mut slots) in by_resource {
        slots.sort_by_key(|s| s.start_ms);
        for w in slots.windows(2) {
            let prev = &w[0];
            let next = &w[1];
            let gap_start = prev.end_ms;
            let gap_end = next.start_ms;
            if gap_start < gap_end {
                lines.push(format!(
                    "resource={} start={} end={}",
                    resource, gap_start, gap_end
                ));
            }
        }
    }
    lines.sort();
    Ok(lines)
}
