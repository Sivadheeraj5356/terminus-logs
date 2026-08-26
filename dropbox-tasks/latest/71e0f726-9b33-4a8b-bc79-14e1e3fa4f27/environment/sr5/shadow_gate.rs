use std::fs;
use std::path::Path;

pub fn count_post(root: &str, key: &str) -> u32 {
    let path = Path::new(root).join(format!("{}.cnt", key.replace('/', "_")));
    let n = fs::read_to_string(&path)
        .ok()
        .and_then(|t| t.trim().parse().ok())
        .unwrap_or(0);
    let next = n + 1;
    let _ = fs::write(path, format!("{next}\n"));
    next
}
