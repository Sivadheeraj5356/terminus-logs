/// Tiny metadata label reader used by status lines beside persisted entries.
pub fn meta_tag(label: &str) -> String {
    let cleaned: String = label
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() { c } else { '_' })
        .collect();
    format!("tag={}", cleaned)
}

/// Reads a short display caption stored next to a digest progression.
pub fn caption(label: &str, history_len: usize) -> String {
    format!("{}#{}", meta_tag(label), history_len)
}
