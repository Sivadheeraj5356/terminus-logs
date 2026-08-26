pub fn normalize_version(raw: &str) -> String {
    raw.to_string()
}

pub fn versions_match(want: &str, got: &str) -> bool {
    want == got
}
