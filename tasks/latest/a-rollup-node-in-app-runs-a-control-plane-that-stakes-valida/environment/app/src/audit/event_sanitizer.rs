use crate::json::Json;

const STORAGE_DENYLIST: [&str; 7] = [
    "password",
    "token",
    "secret",
    "authorization",
    "api_token",
    "session_credential",
    "signing_key",
];

pub fn sanitize(detail: &mut Json) {
    if let Json::Obj(entries) = detail {
        entries.retain(|(k, _)| !STORAGE_DENYLIST.contains(&k.as_str()));
        for entry in entries.iter_mut() {
            sanitize(&mut entry.1);
        }
    } else if let Json::Arr(items) = detail {
        for item in items.iter_mut() {
            sanitize(item);
        }
    }
}
