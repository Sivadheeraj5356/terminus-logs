use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use serde_json::Value;

use crate::types::{
    read_utf8, BufferIn, BufferState, EventIn, EventRec, MAX_U64,
};

fn collect_jsonl(base: &Path, dir: &Path, out: &mut Vec<(PathBuf, String)>) -> Result<(), ()> {
    for entry in std::fs::read_dir(dir).map_err(|_| ())? {
        let entry = entry.map_err(|_| ())?;
        let path = entry.path();
        if path.is_dir() {
            collect_jsonl(base, &path, out)?;
        } else if path.extension().and_then(|s| s.to_str()) == Some("jsonl") {
            let rel = path
                .strip_prefix(base)
                .map_err(|_| ())?
                .to_string_lossy()
                .replace('\\', "/");
            out.push((path, rel));
        }
    }
    Ok(())
}

pub fn load_buffers(task: &Path) -> Result<BTreeMap<String, BufferState>, ()> {
    let path = task.join("config").join("buffers.json");
    let text = read_utf8(&path)?;
    if text.trim().is_empty() {
        return Err(());
    }
    let inputs: Vec<BufferIn> = serde_json::from_str(&text).map_err(|_| ())?;
    if inputs.is_empty() {
        return Err(());
    }
    let mut out = BTreeMap::new();
    for b in inputs {
        if b.buffer_id.is_empty()
            || b.capacity > MAX_U64
            || !matches!(b.status.as_str(), "OPEN" | "HOLD")
            || out.contains_key(&b.buffer_id)
        {
            return Err(());
        }
        out.insert(
            b.buffer_id.clone(),
            BufferState {
                capacity: b.capacity,
                status: b.status,
                filled: 0,
                holdback: 0,
                dispatched: 0,
                lane_filled: BTreeMap::new(),
                lane_holdback: BTreeMap::new(),
            },
        );
    }
    Ok(out)
}

pub fn load_events(task: &Path) -> Result<Vec<EventRec>, ()> {
    let dir = task.join("events");
    if !dir.is_dir() {
        return Err(());
    }
    let mut files = Vec::new();
    collect_jsonl(&dir, &dir, &mut files)?;
    files.sort_by(|a, b| a.1.cmp(&b.1));
    if files.is_empty() {
        return Err(());
    }
    let mut events = Vec::new();
    for (path, rel) in files {
        let text = read_utf8(&path)?;
        let normalized = text.replace("\r\n", "\n").replace('\r', "\n");
        for (idx, line) in normalized.lines().enumerate() {
            if line.trim().is_empty() {
                continue;
            }
            let value: Value = serde_json::from_str(line).map_err(|_| ())?;
            if !value.is_object() {
                continue;
            }
            let event: EventIn = serde_json::from_value(value).map_err(|_| ())?;
            if event.event_id.is_empty()
                || event.buffer_id.is_empty()
                || !matches!(
                    event.op.as_str(),
                    "INGEST" | "HOLDBACK" | "DISPATCH" | "COMMIT" | "RELEASE" | "TRANSFER"
                        | "PAUSE" | "UNPAUSE"
                )
            {
                return Err(());
            }
            events.push(EventRec {
                rel: rel.clone(),
                line: (idx + 1) as u64,
                event,
            });
        }
    }
    events.sort_by(|a, b| {
        a.event
            .timestamp
            .cmp(&b.event.timestamp)
            .then_with(|| a.rel.cmp(&b.rel))
            .then_with(|| a.line.cmp(&b.line))
    });
    Ok(events)
}
