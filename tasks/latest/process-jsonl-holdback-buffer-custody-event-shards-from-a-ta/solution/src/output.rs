use std::collections::BTreeMap;
use std::fs;

use serde_json::Value;

use crate::types::{
    AuditRow, BufferOut, BufferState, OUT_DIR, RejectRow, ResultOut, SummaryOut,
};

fn sort_keys(value: &Value) -> Value {
    use serde_json::{Map, Value};
    match value {
        Value::Object(map) => {
            let mut out = Map::new();
            let mut keys: Vec<_> = map.keys().cloned().collect();
            keys.sort();
            for key in keys {
                out.insert(key.clone(), sort_keys(&map[&key]));
            }
            Value::Object(out)
        }
        Value::Array(arr) => Value::Array(arr.iter().map(sort_keys).collect()),
        other => other.clone(),
    }
}

pub fn write_all(
    buffers: &BTreeMap<String, BufferState>,
    audit: &[AuditRow],
    rejects: &[RejectRow],
    duplicate_events: u64,
) -> Result<(), ()> {
    let mut buffer_vec = Vec::new();
    let mut total_filled = 0u64;
    let mut total_holdback = 0u64;
    let mut total_dispatched = 0u64;
    for (id, state) in buffers {
        total_filled += state.filled;
        total_holdback += state.holdback;
        total_dispatched += state.dispatched;
        buffer_vec.push(BufferOut {
            available: state.available(),
            buffer_id: id.clone(),
            capacity: state.capacity,
            dispatched: state.dispatched,
            filled: state.filled,
            holdback: state.holdback,
            status: state.status.clone(),
        });
    }
    buffer_vec.sort_by(|a, b| a.buffer_id.cmp(&b.buffer_id));
    let result = ResultOut {
        buffers: buffer_vec,
        summary: SummaryOut {
            applied_events: audit.len() as u64,
            buffers_total: buffers.len() as u64,
            duplicate_events,
            rejected_events: rejects.len() as u64,
            total_dispatched,
            total_filled,
            total_holdback,
        },
    };
    let root = serde_json::to_value(&result).map_err(|_| ())?;
    let mut json = serde_json::to_string_pretty(&sort_keys(&root)).map_err(|_| ())?;
    json.push('\n');
    fs::write(format!("{OUT_DIR}/result.json"), json).map_err(|_| ())?;

    let mut audit_text = String::from("event_id,timestamp,buffer_id,lane_id,applied_qty\n");
    for r in audit {
        audit_text.push_str(&format!(
            "{},{},{},{},{}\n",
            r.event_id, r.timestamp, r.buffer_id, r.lane_id, r.applied_qty
        ));
    }
    fs::write(format!("{OUT_DIR}/audit.csv"), audit_text).map_err(|_| ())?;

    let mut reject_text = String::from("event_id,timestamp,buffer_id,reason\n");
    for r in rejects {
        reject_text.push_str(&format!(
            "{},{},{},{}\n",
            r.event_id, r.timestamp, r.buffer_id, r.reason
        ));
    }
    fs::write(format!("{OUT_DIR}/rejects.csv"), reject_text).map_err(|_| ())?;
    Ok(())
}
