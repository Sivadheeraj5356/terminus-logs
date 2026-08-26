pub fn legacy_affinity_label(left: &str, right: &str) -> String {
    format!("{}::{}", left.trim(), right.trim())
}
