pub fn wants_log(verbs: &[u32]) -> bool {
    verbs.iter().any(|v| *v == 1)
}

pub fn wants_check(verbs: &[u32]) -> bool {
    verbs.iter().any(|v| *v == 2 || *v == 4)
}

pub fn mark_id(path: &str) -> String {
    if let Some(idx) = path.rfind('/') {
        if idx > 0 {
            return path[..idx].to_string();
        }
    }
    path.to_string()
}
