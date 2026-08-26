use crate::journal::OpEntry;
use std::collections::{HashMap, HashSet};

pub fn finalize_order(mut rows: Vec<OpEntry>) -> Result<Vec<OpEntry>, String> {
    rows.sort_by_key(|entry| entry.seq);
    let mut seen_seq: HashMap<u64, String> = HashMap::new();
    let mut seen_event: HashSet<String> = HashSet::new();
    let mut out = Vec::new();
    for entry in rows {
        let fp = entry.durable_fingerprint();
        if let Some(prior) = seen_seq.get(&entry.seq) {
            if prior != &fp {
                return Err(format!("conflicting durable seq {}", entry.seq));
            }
            continue;
        }
        if !entry.event_id.is_empty() && !seen_event.insert(entry.event_id.clone()) {
            continue;
        }
        seen_seq.insert(entry.seq, fp);
        out.push(entry);
    }
    Ok(out)
}
