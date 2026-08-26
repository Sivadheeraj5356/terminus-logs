pub fn normalize_version(raw: &str) -> String {
    raw.split('+').next().unwrap_or(raw).to_string()
}

pub fn versions_match(want: &str, got: &str) -> bool {
    normalize_version(want) == normalize_version(got)
}
