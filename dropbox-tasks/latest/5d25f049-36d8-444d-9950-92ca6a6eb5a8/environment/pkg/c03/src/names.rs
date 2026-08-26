pub fn visible_name(kind: &str, id: &str, revision: &str) -> String {
    let short = &revision[..8.min(revision.len())];
    format!("pol-{kind}-{id}-{short}")
}
