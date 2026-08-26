use crate::export::atlas::AtlasArtifact;
use serde_json::Value;

pub fn compute_witness(atlas: &AtlasArtifact) -> String {
    let payload = serde_json::json!({
        "expedition_id": atlas.expedition_id,
        "anchor_obs_id": atlas.anchor_obs_id,
        "observation_count": atlas.observation_count,
        "observations": atlas.observations,
        "dive_lanes": atlas.dive_lanes,
    });
    let canonical = canonical_json_string(&payload);
    format!("{:08x}", crc32fast::hash(canonical.as_bytes()))
}

fn canonical_json_string(value: &Value) -> String {
    match value {
        Value::Null => "null".to_string(),
        Value::Bool(b) => b.to_string(),
        Value::Number(n) => n.to_string(),
        Value::String(s) => serde_json::to_string(s).unwrap_or_else(|_| String::new()),
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
                        serde_json::to_string(key).unwrap_or_else(|_| String::new()),
                        canonical_json_string(&map[*key])
                    )
                })
                .collect();
            format!("{{{}}}", parts.join(","))
        }
    }
}
