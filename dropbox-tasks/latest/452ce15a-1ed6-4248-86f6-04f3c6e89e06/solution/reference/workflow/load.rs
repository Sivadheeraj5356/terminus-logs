use std::path::Path;

use crate::folio::bind::merge_batch;
use crate::types::ChipProfile;

pub fn load_chip_files(paths: &[impl AsRef<Path>], as_of: &str) -> Result<ChipProfile, String> {
    let merged = merge_batch(paths, as_of)?;
    let mut ids: Vec<String> = merged.families.keys().cloned().collect();
    ids.sort();
    let first = ids
        .first()
        .ok_or_else(|| "no families".to_string())?;
    Ok(merged
        .families
        .get(first)
        .ok_or_else(|| "missing family".to_string())?
        .profile
        .clone())
}
