pub fn canonical(path: &str) -> String {
    let mut parts: Vec<&str> = Vec::new();
    for seg in path.split('/') {
        if seg.is_empty() || seg == "." {
            continue;
        }
        if seg == ".." {
            parts.pop();
            continue;
        }
        parts.push(seg);
    }
    if parts.is_empty() {
        return "/".to_string();
    }
    format!("/{}", parts.join("/"))
}
