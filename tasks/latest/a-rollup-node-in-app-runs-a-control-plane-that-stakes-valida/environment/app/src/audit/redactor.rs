use crate::json::Json;

const SENSITIVE_KEYS: [&str; 8] = [
    "password",
    "token",
    "secret",
    "authorization",
    "api_token",
    "session_credential",
    "settlement_credential",
    "signing_key",
];

pub fn redact(value: &mut Json) {
    if let Json::Obj(entries) = value {
        for entry in entries.iter_mut() {
            if SENSITIVE_KEYS.contains(&entry.0.as_str()) {
                entry.1 = Json::Str("[redacted]".to_string());
            } else {
                redact(&mut entry.1);
            }
        }
    } else if let Json::Arr(items) = value {
        for item in items.iter_mut() {
            redact(item);
        }
    }
}
