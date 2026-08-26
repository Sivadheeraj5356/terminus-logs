use std::path::{Path, PathBuf};

use super::staging::StagingArtifact;

pub fn resolve_bundle_path(bundle: &Path) -> PathBuf {
    if bundle.is_absolute() {
        return bundle.to_path_buf();
    }
    if bundle.components().count() == 1 {
        return PathBuf::from("/app/data/dives").join(bundle);
    }
    bundle.to_path_buf()
}

pub fn persist_snapshot(artifact: &StagingArtifact) -> Result<(), i32> {
    let dir = Path::new("/app/state");
    std::fs::create_dir_all(dir).ok();
    let path = dir.join(format!("{}-dives.json", artifact.expedition_id));
    let json = serde_json::to_string_pretty(artifact).map_err(|_| 1)?;
    std::fs::write(path, json).map_err(|_| 1)?;
    Ok(())
}
