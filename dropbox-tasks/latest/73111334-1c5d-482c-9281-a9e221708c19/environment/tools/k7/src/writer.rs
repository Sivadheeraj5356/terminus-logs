use core_k::LedgerDoc;
use std::fs;
use std::path::Path;

pub fn write_ledger(path: &Path, doc: &LedgerDoc) -> std::io::Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let raw = serde_json::to_string_pretty(doc).unwrap_or_else(|_| "{}".to_string());
    fs::write(path, raw)
}
