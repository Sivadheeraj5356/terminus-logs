use crate::model::Event;
use sha2::{Digest, Sha256};

pub fn transcript_digest(events: &[Event]) -> String {
    let raw = serde_json::to_string(events).unwrap_or_else(|_| "[]".to_string());
    let mut h = Sha256::new();
    h.update(raw.as_bytes());
    format!("sha256:{:x}", h.finalize())
}
