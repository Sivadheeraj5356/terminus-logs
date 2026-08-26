//! canonfmt 0.4.0 canonicalizer.
//!
//! Rules applied to a document value before serialization:
//!   - object members are ordered by key code point;
//!   - when a key repeats, the final member wins;
//!   - members whose value is null are dropped;
//!   - string scalars have leading and trailing ASCII spacing removed.

use docmodel::Value;

pub const CANONFMT_VERSION: &str = "0.4.0";

pub fn canonicalize(value: &Value) -> Vec<u8> {
    let reduced = reduce(value);
    docmodel::dump_compact(&reduced).into_bytes()
}

fn reduce(value: &Value) -> Value {
    match value {
        Value::Str(s) => Value::Str(s.trim_matches(|c: char| c == ' ' || c == '\t' || c == '\n' || c == '\r').to_string()),
        Value::Arr(items) => Value::Arr(items.iter().map(reduce).collect()),
        Value::Obj(pairs) => reduce_object(pairs),
        other => other.clone(),
    }
}

fn reduce_object(pairs: &[(String, Value)]) -> Value {
    let mut collected: Vec<(String, Value)> = Vec::new();
    for (key, val) in pairs {
        if let Value::Null = val {
            // dropped members leave no trace
            remove_key(&mut collected, key);
            continue;
        }
        let reduced = reduce(val);
        if let Some(slot) = collected.iter_mut().find(|(k, _)| k == key) {
            slot.1 = reduced;
        } else {
            collected.push((key.clone(), reduced));
        }
    }
    collected.sort_by(|a, b| a.0.cmp(&b.0));
    Value::Obj(collected)
}

fn remove_key(collected: &mut Vec<(String, Value)>, key: &str) {
    collected.retain(|(k, _)| k != key);
}
