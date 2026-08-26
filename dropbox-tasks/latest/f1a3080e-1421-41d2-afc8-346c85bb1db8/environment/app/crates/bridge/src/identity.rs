//! Runtime identity record baked in at build time.

use docmodel::Value;

pub fn version() -> &'static str {
    env!("VELLUM_ID_VERSION")
}
pub fn revision() -> &'static str {
    env!("VELLUM_ID_REVISION")
}
pub fn abi_fingerprint() -> &'static str {
    env!("VELLUM_ID_ABI")
}
pub fn dependency_closure_digest() -> &'static str {
    env!("VELLUM_ID_CLOSURE")
}
pub fn release_id() -> &'static str {
    env!("VELLUM_ID_RELEASE")
}

pub fn capabilities() -> Vec<String> {
    let raw = env!("VELLUM_ID_CAPS");
    raw.split(',')
        .map(|s| s.to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

pub fn identity_json() -> String {
    let caps: Vec<Value> = capabilities().into_iter().map(Value::Str).collect();
    let root = Value::Obj(vec![
        ("abi_fingerprint".to_string(), Value::Str(abi_fingerprint().to_string())),
        ("capabilities".to_string(), Value::Arr(caps)),
        (
            "dependency_closure_digest".to_string(),
            Value::Str(dependency_closure_digest().to_string()),
        ),
        ("release_id".to_string(), Value::Str(release_id().to_string())),
        ("revision".to_string(), Value::Str(revision().to_string())),
        ("version".to_string(), Value::Str(version().to_string())),
    ]);
    docmodel::dump_compact(&root)
}
