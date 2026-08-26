use std::fs;
use std::path::Path;

use crate::probe::parse::parse_chip_text;
use crate::types::ChipProfile;

pub fn load_chip(path: &Path) -> Result<ChipProfile, String> {
    let raw = fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
    parse_chip_text(path, &raw)
}
