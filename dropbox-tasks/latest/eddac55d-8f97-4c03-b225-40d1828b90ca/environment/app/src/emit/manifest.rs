use std::collections::BTreeMap;

use serde_json::{json, Value};

use crate::emit::tzif::{serialize, sha256_hex};
use crate::timeline::Zone;

/// Canonical JSON: object keys sorted, compact separators, one trailing newline.
pub fn manifest_bytes(zones: &BTreeMap<String, Zone>) -> Vec<u8> {
    let entries: Vec<Value> = zones.values().map(|z| {
        let raw = serialize(z);
        json!({
            "zone": z.name,
            "sha256": sha256_hex(&raw),
            "transition_count": z.transitions.len(),
            "first_transition": z.transitions.first().map(|t| t.ut).unwrap_or(0),
            "last_transition": z.transitions.last().map(|t| t.ut).unwrap_or(0),
        })
    }).collect();
    let doc = json!({"version": 1, "zones": entries});
    let mut out = serde_json::to_vec(&doc).expect("canonical json");
    out.push(b'\n');
    out
}
