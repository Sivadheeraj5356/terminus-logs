use std::collections::BTreeMap;
use std::path::Path;

pub fn read_groups(repo_root: &Path) -> BTreeMap<String, Vec<String>> {
    let path = repo_root.join("ledger/fragments.map");
    let Ok(text) = std::fs::read_to_string(path) else {
        return BTreeMap::new();
    };
    let mut out = BTreeMap::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let fields: Vec<&str> = line.split('|').collect();
        if fields.len() < 2 {
            continue;
        }
        out.insert(
            fields[0].to_string(),
            fields[1..].iter().map(|s| s.to_string()).collect(),
        );
    }
    out
}
