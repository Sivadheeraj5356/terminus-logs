use crate::reconcile::merge::FeatureLink;
use serde_json::Value;

pub fn crc32_hex_lower(data: &str) -> String {
    format!("{:08x}", crc32fast::hash(data.as_bytes()))
}

fn canonical_json_string(value: &Value) -> String {
    match value {
        Value::Null => "null".to_string(),
        Value::Bool(b) => b.to_string(),
        Value::Number(n) => n.to_string(),
        Value::String(s) => serde_json::to_string(s).unwrap_or_default(),
        Value::Array(items) => {
            let parts: Vec<String> = items.iter().map(canonical_json_string).collect();
            format!("[{}]", parts.join(","))
        }
        Value::Object(map) => {
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            let parts: Vec<String> = keys
                .iter()
                .map(|key| {
                    format!(
                        "{}:{}",
                        serde_json::to_string(key).unwrap_or_default(),
                        canonical_json_string(&map[*key])
                    )
                })
                .collect();
            format!("{{{}}}", parts.join(","))
        }
    }
}

pub fn staging_bind(expedition_id: &str, report_ids: &[String]) -> String {
    let mut ids = report_ids.to_vec();
    ids.sort();
    let payload = serde_json::json!({
        "expedition_id": expedition_id,
        "report_ids": ids,
    });
    crc32_hex_lower(&canonical_json_string(&payload))
}

pub fn lane_bind(report_ids: &[String]) -> String {
    let mut ids = report_ids.to_vec();
    ids.sort();
    crc32_hex_lower(&format!("{};", ids.join(";")))
}

pub fn reconcile_bind(links: &[FeatureLink]) -> String {
    let payload: Vec<Value> = links
        .iter()
        .map(|link| {
            serde_json::json!({
                "links_to": link.links_to,
                "obs_id": link.obs_id,
            })
        })
        .collect();
    crc32_hex_lower(&canonical_json_string(&Value::Array(payload)))
}

pub fn expedition_seal(atlas_witness: &str, reconcile_bind: &str) -> String {
    crc32_hex_lower(&format!("{atlas_witness}|{reconcile_bind}"))
}
