use crate::q_st::Store;
use std::fs;
use std::path::Path;

/// Parses wal seal records into tag values when the tag sidecar is absent.
pub fn tags_from_wal(root: &Path) -> Vec<u64> {
    let wal_path = root.parent().map(|p| p.join("wal.log")).unwrap_or_default();
    let body = fs::read_to_string(wal_path).unwrap_or_default();
    let mut tags = Vec::new();
    for line in body.lines() {
        if !line.starts_with("seal:") {
            continue;
        }
        let parts: Vec<&str> = line.split(':').collect();
        if parts.len() >= 3 {
            if let Ok(last_tag) = parts[2].parse::<u64>() {
                tags.push(last_tag);
            }
        }
    }
    tags
}

pub fn hydrate_tags(store: &Store) -> Vec<u64> {
    let sidecar = crate::q_st::read_tag_sidecar(store);
    if !sidecar.is_empty() {
        return sidecar;
    }
    tags_from_wal(&store.root)
}
