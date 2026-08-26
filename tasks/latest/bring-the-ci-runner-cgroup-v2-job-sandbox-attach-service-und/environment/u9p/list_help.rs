//! Arm label lister for UI dumps (non-authority).

pub fn list_keys(keys: &[&str]) -> String {
    let mut out = String::new();
    for (i, k) in keys.iter().enumerate() {
        if i > 0 {
            out.push('|');
        }
        out.push_str(k);
    }
    out
}

pub fn list_count(keys: &[&str]) -> usize {
    keys.len()
}
