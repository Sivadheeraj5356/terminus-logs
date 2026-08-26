use crate::codec;
use crate::fragments;
use crate::index;
use crate::model::{Hit, Part};
use crate::paths;
use crate::sweep;
use crate::util;
use std::path::Path;

pub fn phase_b(base: &Path, repo: &str, item: &Part) -> Result<Hit, String> {
    let repo_root = base.join(repo);
    let profiles = base.parent().unwrap_or(base).join("profiles");
    let groups = fragments::read_groups(&repo_root);
    if let Some(frags) = groups.get(&item.id) {
        return merge_frags(base, repo, item, frags, &profiles);
    }
    if let Ok(hit) = read_indexed(base, repo, item, &profiles) {
        return Ok(hit);
    }
    sweep::phase_c(base, repo, item)
}

fn merge_frags(
    base: &Path,
    repo: &str,
    item: &Part,
    frags: &[String],
    profiles: &Path,
) -> Result<Hit, String> {
    let mut buf = Vec::new();
    let mut sources = Vec::new();
    for frag_id in frags {
        let (data, source) = read_fragment(base, repo, frag_id, profiles)?;
        sources.push(format!("{}:{}", frag_id, source));
        buf.extend_from_slice(&data);
    }
    if util::stamp(&buf) != item.mark {
        return Err(format!("{}:{} merge mark mismatch", repo, item.id));
    }
    Ok(Hit {
        data: buf,
        status: "merged".to_string(),
        source: sources.join(","),
    })
}

fn read_fragment(
    base: &Path,
    repo: &str,
    frag_id: &str,
    profiles: &Path,
) -> Result<(Vec<u8>, String), String> {
    let repo_root = base.join(repo);
    let table = index::read_index(&repo_root.join("index/chunks.idx"))?;
    let loc = table
        .get(frag_id)
        .ok_or_else(|| format!("missing fragment {}", frag_id))?;
    let object_path = repo_root.join("objects").join(&loc.object);
    let raw = paths::read_span(&object_path, loc.offset, loc.len)?;
    let data = codec::maybe_unmask_pool(&raw, profiles, repo, &loc.object);
    Ok((
        data,
        format!("{}:{}+{}", loc.object, loc.offset, loc.len),
    ))
}

fn read_indexed(base: &Path, repo: &str, item: &Part, profiles: &Path) -> Result<Hit, String> {
    let repo_root = base.join(repo);
    let table = index::read_index(&repo_root.join("index/chunks.idx"))?;
    let loc = table
        .get(&item.id)
        .ok_or_else(|| format!("missing locator {}", item.id))?;
    let object_path = repo_root.join("objects").join(&loc.object);
    if loc.len != item.len {
        return Err(format!("{}:{} length mismatch", repo, item.id));
    }
    let raw = paths::read_span(&object_path, loc.offset, loc.len)?;
    let data = codec::maybe_unmask_pool(&raw, profiles, repo, &loc.object);
    if util::stamp(&data) != item.mark {
        return Err(format!("{}:{} mark mismatch", repo, item.id));
    }
    Ok(Hit {
        data,
        status: "indexed".to_string(),
        source: format!("{}:{}+{}", loc.object, loc.offset, loc.len),
    })
}
