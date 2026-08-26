use std::collections::HashMap;
use std::path::Path;

use crate::epoch;
use crate::ordering;
use crate::overlap;
use crate::parser::{self, Slot};
use crate::resolve;

#[derive(Debug, Clone)]
struct MergedSlot {
    resource: String,
    start_ms: u64,
    end_ms: u64,
    holder: String,
    source_file: String,
}

impl From<MergedSlot> for Slot {
    fn from(m: MergedSlot) -> Self {
        Slot {
            resource: m.resource,
            start_ms: m.start_ms,
            end_ms: m.end_ms,
            holder: m.holder,
            slot_id: 0,
            epoch: 0,
            source_file: m.source_file,
        }
    }
}

fn merge_intervals(slots: &mut [Slot]) -> Vec<MergedSlot> {
    slots.sort_by_key(|s| s.start_ms);
    let mut out: Vec<MergedSlot> = Vec::new();
    for slot in slots.iter() {
        if let Some(last) = out.last_mut() {
            if overlap::slots_connect(last.end_ms, slot.start_ms) {
                if slot.end_ms > last.end_ms {
                    last.end_ms = slot.end_ms;
                }
                let (holder, source_file) = resolve::choose_holder(
                    &last.holder,
                    &last.source_file,
                    &slot.holder,
                    &slot.source_file,
                );
                last.holder = holder;
                last.source_file = source_file;
                continue;
            }
        }
        out.push(MergedSlot {
            resource: slot.resource.clone(),
            start_ms: slot.start_ms,
            end_ms: slot.end_ms,
            holder: slot.holder.clone(),
            source_file: slot.source_file.clone(),
        });
    }
    out
}

pub fn merge_directory(dir: &str) -> Result<Vec<Slot>, String> {
    let paths = parser::list_slot_files(dir)?;
    if paths.is_empty() {
        return Err("no slots".to_string());
    }

    let mut by_resource: HashMap<String, Vec<Slot>> = HashMap::new();
    for path in &paths {
        let mut per_file: HashMap<String, Vec<Slot>> = HashMap::new();
        for row in parser::read_file(Path::new(path))? {
            per_file
                .entry(row.resource.clone())
                .or_default()
                .push(row);
        }
        for (resource, mut slots) in per_file {
            let current: Vec<Slot> = epoch::max_epoch_rows(&slots);
            let merged: Vec<Slot> = merge_intervals(&mut current.clone())
                .into_iter()
                .map(Slot::from)
                .collect();
            by_resource.entry(resource).or_default().extend(merged);
        }
    }

    let mut out: Vec<Slot> = by_resource.into_values().flatten().collect();
    ordering::sort_slots(&mut out);
    Ok(out)
}

pub fn count_records(dir: &str) -> Result<(usize, usize), String> {
    let paths = parser::list_slot_files(dir)?;
    if paths.is_empty() {
        return Err("no slots".to_string());
    }
    let mut records = 0usize;
    for path in &paths {
        records += parser::read_file(Path::new(path))?.len();
    }
    Ok((paths.len(), records))
}
