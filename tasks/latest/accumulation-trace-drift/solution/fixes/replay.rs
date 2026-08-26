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
        let rest = line.strip_prefix("seal:").unwrap_or("");
        let mut parts = rest.splitn(2, ':');
        let _step = parts.next();
        if let Some(tag_csv) = parts.next() {
            for token in tag_csv.split(',') {
                if token.is_empty() {
                    continue;
                }
                if let Ok(tag) = token.parse::<u64>() {
                    tags.push(tag);
                }
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
