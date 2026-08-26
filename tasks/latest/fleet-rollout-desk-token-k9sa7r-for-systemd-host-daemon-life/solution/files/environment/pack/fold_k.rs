use crate::persist::phase_rank;
use serde_json::{Map, Value};

fn sort_key(row: &Value) -> (i64, u8, String, String, i64) {
    let scenario = row.get("scenario").and_then(|v| v.as_i64()).unwrap_or(0);
    let phase = row.get("phase").and_then(|v| v.as_str()).unwrap_or("");
    let member = row.get("target").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let marker = row.get("marker").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let sequence = row.get("sequence").and_then(|v| v.as_i64()).unwrap_or(0);
    (scenario, phase_rank(phase), member, marker, sequence)
}

/// folds per-phase rows into ordered trace records.
pub fn fold_k(left: &[Value], right: &[Value]) -> Vec<Value> {
    let required = ["scenario", "phase", "target", "marker", "sequence", "epoch"];
    let mut out: Vec<Value> = left
        .iter()
        .chain(right.iter())
        .filter(|row| required.iter().all(|f| row.get(*f).is_some()))
        .cloned()
        .collect();
    out.sort_by(|a, b| sort_key(a).cmp(&sort_key(b)));
    out
}

pub fn row_map(row: &Value) -> Map<String, Value> {
    row.as_object().cloned().unwrap_or_default()
}
