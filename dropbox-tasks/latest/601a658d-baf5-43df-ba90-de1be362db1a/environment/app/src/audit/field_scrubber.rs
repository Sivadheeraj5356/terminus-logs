use crate::json::Json;

const SCRUB_KEYS: [&str; 7] = [
    "password",
    "secret",
    "session_credential",
    "settlement_credential",
    "signing_key",
    "api_token",
    "authorization",
];

pub fn scrub(value: &mut Json) {
    match value {
        Json::Obj(entries) => {
            entries.retain(|(k, _)| !SCRUB_KEYS.contains(&k.as_str()));
            for entry in entries.iter_mut() {
                scrub(&mut entry.1);
            }
        }
        Json::Arr(items) => {
            for item in items.iter_mut() {
                scrub(item);
            }
        }
        _ => {}
    }
}
