use std::fs;

pub fn count_log_kind(log_path: &str, kind: &str) -> Result<u32, String> {
    let text = fs::read_to_string(log_path).unwrap_or_default();
    let needle = format!("\"{kind}\"");
    let count = text.lines().filter(|line| line.contains(&needle)).count() as u32;
    Ok(count)
}
