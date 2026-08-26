use std::path::Path;

use hx01::model::OwnershipManifest;
use hx01::Result;

pub fn load_roster(path: &Path) -> Result<OwnershipManifest> {
    if !path.exists() {
        return Ok(OwnershipManifest::default());
    }
    let text = std::fs::read_to_string(path)?;
    let manifest: OwnershipManifest = serde_json::from_str(&text)?;
    Ok(manifest)
}

pub fn save_roster(path: &Path, manifest: &OwnershipManifest) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(path, serde_json::to_string_pretty(manifest)?)?;
    Ok(())
}

pub fn audit_append(path: &Path, line: &serde_json::Value) -> Result<()> {
    use std::io::Write;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)?;
    writeln!(file, "{}", line)?;
    Ok(())
}
