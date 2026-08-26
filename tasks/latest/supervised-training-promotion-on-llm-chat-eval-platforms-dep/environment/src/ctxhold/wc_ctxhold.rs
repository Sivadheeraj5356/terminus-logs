pub mod json_io {
    use serde_json::Value;
    use std::fs;
    use std::path::Path;

    pub fn read_json(path: &Path) -> anyhow::Result<Value> {
        let text = fs::read_to_string(path)?;
        Ok(serde_json::from_str(&text)?)
    }

    pub fn write_json(path: &Path, value: &Value) -> anyhow::Result<()> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(path, serde_json::to_string_pretty(value)? + "\n")?;
        Ok(())
    }

    pub fn sort_value(v: &Value) -> Value {
        match v {
            Value::Object(map) => {
                let mut out = serde_json::Map::new();
                let mut keys: Vec<_> = map.keys().cloned().collect();
                keys.sort();
                for k in keys {
                    out.insert(k.clone(), sort_value(&map[&k]));
                }
                Value::Object(out)
            }
            Value::Array(arr) => Value::Array(arr.iter().map(sort_value).collect()),
            other => other.clone(),
        }
    }
}

pub mod digest {
    use sha2::{Digest, Sha256};
    use std::path::Path;

    use super::json_io::{read_json, sort_value};

    pub const MANIFESTS: &[&str] = &[
        "conversation_sessions.json",
        "prompt_turn_log.json",
        "retrieval_injections.json",
        "tool_execution_outputs.json",
        "system_instruction_versions.json",
        "model_output_failures.json",
        "contamination_policy.json",
        "session_order_timeline.json",
    ];

    pub fn corpus_stamp(data: &Path) -> anyhow::Result<String> {
        let mut hasher = Sha256::new();
        for name in MANIFESTS {
            let v = read_json(&data.join(name))?;
            let compact = serde_json::to_string(&sort_value(&v))?;
            hasher.update(compact.as_bytes());
        }
        Ok(hex::encode(hasher.finalize()))
    }
}

pub mod dedupe {
    use serde_json::Value;
    use std::collections::BTreeMap;

    pub fn dedupe_last_wins(arr: &[Value], key: &str) -> Vec<Value> {
        let mut map: BTreeMap<String, Value> = BTreeMap::new();
        let mut order: Vec<String> = Vec::new();
        for item in arr {
            if let Some(Value::String(id)) = item.get(key) {
                if !map.contains_key(id) {
                    order.push(id.clone());
                }
                map.insert(id.clone(), item.clone());
            }
        }
        order
            .into_iter()
            .filter_map(|id| map.remove(&id))
            .collect()
    }
}

pub use digest::corpus_stamp;
pub use json_io::{read_json, sort_value, write_json};
