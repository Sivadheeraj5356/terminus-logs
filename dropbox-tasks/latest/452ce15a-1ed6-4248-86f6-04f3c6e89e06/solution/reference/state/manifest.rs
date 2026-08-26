use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};

use sha2::{Digest, Sha256};

use crate::types::{
    ManifestBranch, ManifestHistoryEntry, ResonanceManifest, MANIFEST_SCHEMA_VERSION,
};

pub fn manifest_path() -> PathBuf {
    PathBuf::from("/app/output/resonance_manifest.json")
}

pub fn read_manifest() -> ResonanceManifest {
    let raw = match fs::read_to_string(manifest_path()) {
        Ok(raw) => raw,
        Err(_) => {
            return ResonanceManifest {
                schema_version: MANIFEST_SCHEMA_VERSION,
                batch_generation: 0,
                last_input_fingerprint: String::new(),
                last_profile_graph_hash: String::new(),
                branches: Vec::new(),
                history: Vec::new(),
            };
        }
    };
    serde_json::from_str(&raw).unwrap_or(ResonanceManifest {
        schema_version: MANIFEST_SCHEMA_VERSION,
        batch_generation: 0,
        last_input_fingerprint: String::new(),
        last_profile_graph_hash: String::new(),
        branches: Vec::new(),
        history: Vec::new(),
    })
}

fn write_manifest(manifest: &ResonanceManifest) -> Result<(), String> {
    let raw =
        serde_json::to_string_pretty(manifest).map_err(|e| format!("manifest json: {e}"))?;
    if let Some(parent) = manifest_path().parent() {
        fs::create_dir_all(parent).map_err(|e| format!("manifest dir: {e}"))?;
    }
    fs::write(manifest_path(), format!("{raw}\n"))
        .map_err(|e| format!("manifest write: {e}"))
}

pub fn resolve_batch_generation(
    input_fingerprint: &str,
    profile_graph_hash: &str,
) -> u32 {
    let manifest = read_manifest();
    if manifest.last_input_fingerprint == input_fingerprint
        && manifest.last_profile_graph_hash == profile_graph_hash
    {
        return manifest.batch_generation.max(1);
    }
    for entry in &manifest.history {
        if entry.input_fingerprint == input_fingerprint
            && entry.profile_graph_hash == profile_graph_hash
        {
            return entry.batch_generation.max(1);
        }
    }
    let max_gen = manifest
        .history
        .iter()
        .map(|e| e.batch_generation)
        .max()
        .unwrap_or(0);
    if max_gen == 0 {
        1
    } else {
        max_gen + 1
    }
}

pub fn resolve_branch_generation(
    family_id: &str,
    input_fingerprint: &str,
    profile_graph_hash: &str,
    batch_generation: u32,
    batch_key_is_new: bool,
) -> u32 {
    let manifest = read_manifest();
    for branch in &manifest.branches {
        if branch.family_id == family_id
            && branch.input_fingerprint == input_fingerprint
            && branch.profile_graph_hash == profile_graph_hash
        {
            return branch.branch_generation.max(1);
        }
    }
    let max_branch = manifest
        .branches
        .iter()
        .map(|b| b.branch_generation)
        .max()
        .unwrap_or(0);
    let _ = (batch_generation, batch_key_is_new);
    if max_branch == 0 {
        1
    } else {
        max_branch + 1
    }
}

pub fn commit_success(
    input_fingerprint: &str,
    profile_graph_hash: &str,
    batch_generation: u32,
    family_branches: &[(String, u32)],
    batch_key_is_new: bool,
) -> Result<(), String> {
    let mut manifest = read_manifest();
    let history_entry = ManifestHistoryEntry {
        batch_generation,
        input_fingerprint: input_fingerprint.to_string(),
        profile_graph_hash: profile_graph_hash.to_string(),
    };
    if !manifest.history.iter().any(|entry| {
        entry.input_fingerprint == history_entry.input_fingerprint
            && entry.profile_graph_hash == history_entry.profile_graph_hash
    }) {
        manifest.history.push(history_entry);
    }
    manifest.batch_generation = batch_generation;
    manifest.last_input_fingerprint = input_fingerprint.to_string();
    manifest.last_profile_graph_hash = profile_graph_hash.to_string();
    manifest.schema_version = MANIFEST_SCHEMA_VERSION;

    for (family_id, branch_generation) in family_branches {
        let parent = if batch_key_is_new {
            Some(batch_generation.saturating_sub(1).max(1))
        } else {
            None
        };
        let new_branch = ManifestBranch {
            family_id: family_id.clone(),
            branch_generation: *branch_generation,
            input_fingerprint: input_fingerprint.to_string(),
            profile_graph_hash: profile_graph_hash.to_string(),
            parent_branch_generation: parent,
        };
        if let Some(existing) = manifest.branches.iter_mut().find(|b| {
            b.family_id == *family_id
                && b.input_fingerprint == input_fingerprint
                && b.profile_graph_hash == profile_graph_hash
        }) {
            *existing = new_branch;
        } else {
            manifest.branches.push(new_branch);
        }
    }
    write_manifest(&manifest)
}

pub fn fingerprint_inputs(
    paths: &[impl AsRef<Path>],
    as_of: &str,
) -> Result<String, String> {
    let mut hasher = Sha256::new();
    hasher.update(as_of.as_bytes());
    hasher.update(b"\n");
    for path in paths {
        let path_ref = path.as_ref();
        hasher.update(path_ref.display().to_string().as_bytes());
        hasher.update(b"\n");
        let bytes = fs::read(path_ref).map_err(|e| format!("{}: {e}", path_ref.display()))?;
        hasher.update(&bytes);
        hasher.update(b"\n");
    }
    Ok(format!("sha256:{}", hex::encode(hasher.finalize())))
}

pub fn source_digest(path: &Path) -> Result<String, String> {
    let mut file = fs::File::open(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut bytes = Vec::new();
    file.read_to_end(&mut bytes)
        .map_err(|e| format!("{}: {e}", path.display()))?;
    Ok(format!("sha256:{}", hex::encode(Sha256::digest(&bytes))))
}
