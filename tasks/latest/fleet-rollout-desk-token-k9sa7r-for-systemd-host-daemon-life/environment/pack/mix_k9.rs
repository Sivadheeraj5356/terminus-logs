use serde_json::Value;
use sha2::{Digest, Sha256};

pub fn fingerprint(rows: &[Value]) -> String {
    let mut parts: Vec<String> = Vec::new();
    for row in rows {
        let scenario = row.get("scenario").and_then(|v| v.as_i64()).unwrap_or(0);
        let phase = row.get("phase").and_then(|v| v.as_str()).unwrap_or("");
        let member = row.get("target").and_then(|v| v.as_str()).unwrap_or("");
        let marker = row.get("marker").and_then(|v| v.as_str()).unwrap_or("");
        let sequence = row.get("sequence").and_then(|v| v.as_i64()).unwrap_or(0);
        let epoch = row.get("epoch").and_then(|v| v.as_i64()).unwrap_or(0);
        parts.push(format!("{scenario},{phase},{member},{marker},{sequence},{epoch}"));
    }
    parts.sort();
    let payload = parts.join("\n") + "\n";
    format!("{:x}", Sha256::digest(payload.as_bytes()))
}
