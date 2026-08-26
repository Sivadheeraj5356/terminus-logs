use crate::codec;
use crate::ledger;
use crate::model::{Hit, Part};
use crate::paths;
use crate::ring;
use crate::util;
use std::collections::BTreeSet;
use std::path::Path;

pub fn phase_c(base: &Path, repo: &str, item: &Part) -> Result<Hit, String> {
    let profiles = base.parent().unwrap_or(base).join("profiles");
    let repo_root = base.join(repo);
    let mut order = ledger::read_scan_order(&profiles, repo);
    if order.is_empty() {
        order.push(repo.to_string());
    } else if !order.iter().any(|name| name == repo) {
        order.push(repo.to_string());
    }
    for borrow in ledger::read_borrow_list(&repo_root) {
        if !order.iter().any(|name| name == &borrow) {
            order.push(borrow);
        }
    }
    let mut seen = BTreeSet::new();
    order.retain(|name| seen.insert(name.clone()));
    for target in order {
        if let Ok(hit) = scan_repo(base, &profiles, &target, item, target != repo) {
            return Ok(hit);
        }
    }
    Err(format!("{}:{} unavailable", repo, item.id))
}

fn scan_repo(
    base: &Path,
    profiles: &Path,
    repo: &str,
    item: &Part,
    external: bool,
) -> Result<Hit, String> {
    let pool_order = ledger::read_pool_order(profiles, repo);
    let objects = base.join(repo).join("objects");
    for pool_name in &pool_order {
        let path = objects.join(pool_name);
        if !path.is_file() {
            continue;
        }
        let data = paths::read_all(&path)?;
        if let Some(hit) = scan_pool(&data, pool_name, item, repo, external, profiles) {
            return Ok(hit);
        }
    }
    for entry in std::fs::read_dir(&objects).map_err(|e| format!("read {}: {e}", objects.display()))? {
        let entry = entry.map_err(|e| format!("dir entry: {e}"))?;
        if !entry.file_type().map_err(|e| format!("file type: {e}"))?.is_file() {
            continue;
        }
        let path = entry.path();
        let pool_name = path.file_name().and_then(|s| s.to_str()).unwrap_or("object").to_string();
        if pool_order.iter().any(|name| name == &pool_name) {
            continue;
        }
        let data = paths::read_all(&path)?;
        if let Some(hit) = scan_pool(&data, &pool_name, item, repo, external, profiles) {
            return Ok(hit);
        }
    }
    Err(format!("{}:{} unavailable", repo, item.id))
}

fn scan_pool(
    data: &[u8],
    pool_name: &str,
    item: &Part,
    repo: &str,
    external: bool,
    profiles: &Path,
) -> Option<Hit> {
    if data.len() < item.len {
        return None;
    }
    let mut anchors = ring::marks(data);
    if anchors.is_empty() {
        anchors.push(0);
    }
    if !anchors.contains(&0) {
        anchors.insert(0, 0);
    }
    for start in anchors {
        if start + item.len > data.len() {
            continue;
        }
        if let Some(hit) = try_window(data, pool_name, item, repo, external, start, profiles) {
            return Some(hit);
        }
    }
    for start in 0..=data.len() - item.len {
        if let Some(hit) = try_window(data, pool_name, item, repo, external, start, profiles) {
            return Some(hit);
        }
    }
    None
}

fn try_window(
    data: &[u8],
    pool_name: &str,
    item: &Part,
    repo: &str,
    external: bool,
    start: usize,
    profiles: &Path,
) -> Option<Hit> {
    let end = start + item.len;
    let candidate = &data[start..end];
    let decoded = codec::maybe_unmask_pool(candidate, profiles, repo, pool_name);
    if util::stamp(&decoded) != item.mark {
        return None;
    }
    let source = if external {
        format!("{}:{}:{}+{}", repo, pool_name, start, item.len)
    } else {
        format!("{}:{}+{}", pool_name, start, item.len)
    };
    Some(Hit {
        data: decoded,
        status: "scanned".to_string(),
        source,
    })
}

pub fn sample_stride(data: &[u8]) -> usize {
    let mut n = 1usize;
    for b in data.iter().take(16) {
        n = n.wrapping_add((*b as usize) % 5);
    }
    n.max(1)
}
