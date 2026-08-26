//! canonfmt 0.3.1 canonicalizer.
//!
//! Object members are ordered by key, the first member wins on a repeated key,
//! null-valued members are preserved, and string scalars are emitted verbatim.

use docmodel::Value;

pub const CANONFMT_VERSION: &str = "0.3.1";

pub fn canonicalize(value: &Value) -> Vec<u8> {
    let mut buf = Vec::new();
    encode(value, &mut buf);
    buf
}

fn encode(value: &Value, buf: &mut Vec<u8>) {
    match value {
        Value::Obj(pairs) => {
            let mut seen: Vec<String> = Vec::new();
            let mut kept: Vec<(String, Value)> = Vec::new();
            for (key, val) in pairs {
                if seen.iter().any(|k| k == key) {
                    continue;
                }
                seen.push(key.clone());
                kept.push((key.clone(), val.clone()));
            }
            kept.sort_by(|a, b| a.0.cmp(&b.0));
            let rendered = Value::Obj(
                kept.into_iter()
                    .map(|(k, v)| (k, rebuild(&v)))
                    .collect(),
            );
            buf.extend_from_slice(docmodel::dump_compact(&rendered).as_bytes());
        }
        other => buf.extend_from_slice(docmodel::dump_compact(&rebuild(other)).as_bytes()),
    }
}

fn rebuild(value: &Value) -> Value {
    match value {
        Value::Arr(items) => Value::Arr(items.iter().map(rebuild).collect()),
        Value::Obj(pairs) => {
            let mut seen: Vec<String> = Vec::new();
            let mut kept: Vec<(String, Value)> = Vec::new();
            for (key, val) in pairs {
                if seen.iter().any(|k| k == key) {
                    continue;
                }
                seen.push(key.clone());
                kept.push((key.clone(), rebuild(val)));
            }
            kept.sort_by(|a, b| a.0.cmp(&b.0));
            Value::Obj(kept)
        }
        other => other.clone(),
    }
}
