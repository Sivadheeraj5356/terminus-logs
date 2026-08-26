use std::fs;

/// Diagnostic helper: reports the stale port file contents.
pub fn resolve_d() -> Result<u16, String> {
    let text = fs::read_to_string("/app/environment/vault/stale_port.txt")
        .map_err(|e| e.to_string())?;
    text.trim()
        .parse()
        .map_err(|e: std::num::ParseIntError| e.to_string())
}
