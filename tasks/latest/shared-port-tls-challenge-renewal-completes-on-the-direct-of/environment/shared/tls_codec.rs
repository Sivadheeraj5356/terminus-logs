use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::path::Path;

pub fn read_bytes(root: &Path, rel: &str) -> Vec<u8> {
    std::fs::read(root.join(rel)).unwrap_or_default()
}

pub fn has_marker(pem_bytes: &[u8], marker: &str) -> bool {
    pem_bytes.windows(marker.len()).any(|w| w == marker.as_bytes())
}

pub fn sha256_hex(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    format!("{:x}", hasher.finalize())
}

pub fn epoch_for_slot(slot: &str, epoch_map: &HashMap<String, u32>) -> u32 {
    epoch_map.get(slot).copied().unwrap_or(0)
}

pub fn negotiate_alpn(
    negotiation_class: &str,
    material: &[u8],
    marker: &str,
    rewrite_count: u32,
    codes: &HashMap<String, u32>,
) -> u32 {
    if rewrite_count > 0 && !has_marker(material, marker) {
        return codes.get("stripped").copied().unwrap_or(0);
    }
    if negotiation_class == "app" {
        return codes.get("app_default").copied().unwrap_or(0);
    }
    if has_marker(material, marker) {
        codes.get("challenge").copied().unwrap_or(0)
    } else {
        codes.get("app_default").copied().unwrap_or(0)
    }
}

pub fn plan_order_digest(rows: &[serde_json::Value], plan_hash: &str) -> String {
    let body = format!(
        "{}|[{}]",
        plan_hash,
        rows
            .iter()
            .map(compact_json_value)
            .collect::<Vec<_>>()
            .join(",")
    );
    sha256_hex(body.as_bytes())
}

pub fn manifest_seal_digest(
    rows: &[serde_json::Value],
    compile_generation: u32,
    plan_hash: &str,
    prefix_sep: &str,
) -> String {
    let body = format!(
        "{compile_generation}{prefix_sep}{plan_hash}|[{}]",
        rows
            .iter()
            .map(compact_json_value)
            .collect::<Vec<_>>()
            .join(",")
    );
    sha256_hex(body.as_bytes())
}

fn compact_json_value(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::Object(map) => {
            let mut keys: Vec<&str> = map.keys().map(|k| k.as_str()).collect();
            keys.sort_unstable();
            let inner: Vec<String> = keys
                .into_iter()
                .map(|k| {
                    format!(
                        "\"{}\":{}",
                        k,
                        compact_json_value(&map[k])
                    )
                })
                .collect();
            format!("{{{}}}", inner.join(","))
        }
        serde_json::Value::Array(items) => {
            let inner: Vec<String> = items.iter().map(compact_json_value).collect();
            format!("[{}]", inner.join(","))
        }
        serde_json::Value::String(s) => serde_json::to_string(s).unwrap_or_else(|_| "\"\"".into()),
        serde_json::Value::Number(n) => n.to_string(),
        serde_json::Value::Bool(b) => b.to_string(),
        serde_json::Value::Null => "null".into(),
    }
}

pub fn observation_digest(rows: &[serde_json::Value]) -> String {
    let mut sorted: Vec<&serde_json::Value> = rows.iter().collect();
    sorted.sort_by(|a, b| {
        let ka = (
            a["host_id"].as_str().unwrap_or(""),
            a["lane_id"].as_str().unwrap_or(""),
            a["cohort_label"].as_str().unwrap_or(""),
        );
        let kb = (
            b["host_id"].as_str().unwrap_or(""),
            b["lane_id"].as_str().unwrap_or(""),
            b["cohort_label"].as_str().unwrap_or(""),
        );
        ka.cmp(&kb)
    });
    let body = format!(
        "[{}]",
        sorted
            .iter()
            .map(|row| compact_json_value(row))
            .collect::<Vec<_>>()
            .join(",")
    );
    sha256_hex(body.as_bytes())
}
