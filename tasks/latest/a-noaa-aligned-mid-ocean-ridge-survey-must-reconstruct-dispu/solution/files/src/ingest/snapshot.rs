use std::path::{Path, PathBuf};

use super::staging::StagingArtifact;

pub fn resolve_bundle_path(bundle: &Path) -> PathBuf {
    if bundle.is_absolute() {
        return bundle.to_path_buf();
    }
    if bundle.components().count() == 1 {
        if let Ok(tb3) = std::env::var("TB3_DIVE_DIR") {
            let base = PathBuf::from(&tb3);
            if base.is_absolute() {
                return base.join(bundle);
            }
        }
        return PathBuf::from("/app/data/dives").join(bundle);
    }
    std::env::current_dir()
        .unwrap_or_else(|_| PathBuf::from("/app"))
        .join(bundle)
}

pub fn persist_snapshot(artifact: &StagingArtifact) -> Result<(), i32> {
    let dir = Path::new("/app/state");
    std::fs::create_dir_all(dir).ok();
    let path = dir.join(format!("{}-dives.json", artifact.expedition_id));
    let json = serde_json::to_string_pretty(artifact).map_err(|_| 1)?;
    std::fs::write(path, json).map_err(|_| 1)?;
    Ok(())
}
