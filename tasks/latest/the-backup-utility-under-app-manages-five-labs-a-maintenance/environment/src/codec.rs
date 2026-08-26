use std::collections::BTreeMap;
use std::path::Path;

pub fn xor_bytes(data: &[u8], key: u8) -> Vec<u8> {
    data.iter().map(|b| b ^ key).collect()
}

fn read_profile_map(profiles: &Path, repo: &str) -> BTreeMap<String, String> {
    let mut out = BTreeMap::new();
    let Ok(entries) = std::fs::read_dir(profiles) else {
        return out;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) != Some("conf") {
            continue;
        }
        let Ok(text) = std::fs::read_to_string(&path) else {
            continue;
        };
        let mut name = String::new();
        for line in text.lines() {
            if let Some(rest) = line.trim().strip_prefix("name=") {
                name = rest.to_string();
            }
        }
        if name != repo {
            continue;
        }
        for line in text.lines() {
            let line = line.trim();
            if let Some((key, val)) = line.split_once('=') {
                out.insert(key.trim().to_string(), val.trim().to_string());
            }
        }
        break;
    }
    out
}

pub fn read_mask_key(profiles: &Path, repo: &str) -> Option<u8> {
    let map = read_profile_map(profiles, repo);
    map.get("mask_key")
        .and_then(|v| v.parse::<u8>().ok())
}

pub fn maybe_unmask(data: &[u8], profiles: &Path, repo: &str) -> Vec<u8> {
    match read_mask_key(profiles, repo) {
        Some(key) => xor_bytes(data, key),
        None => data.to_vec(),
    }
}

pub fn masked_pools(profiles: &Path, repo: &str) -> Vec<String> {
    let map = read_profile_map(profiles, repo);
    map.get("masked_pools")
        .map(|v| v.split(',').map(str::trim).filter(|s| !s.is_empty()).map(str::to_string).collect())
        .unwrap_or_default()
}

pub fn maybe_unmask_pool(data: &[u8], profiles: &Path, repo: &str, pool_name: &str) -> Vec<u8> {
    let stem = pool_name.strip_suffix(".blob").unwrap_or(pool_name);
    if masked_pools(profiles, repo).iter().any(|name| name == pool_name || name == stem) {
        return maybe_unmask(data, profiles, repo);
    }
    data.to_vec()
}
