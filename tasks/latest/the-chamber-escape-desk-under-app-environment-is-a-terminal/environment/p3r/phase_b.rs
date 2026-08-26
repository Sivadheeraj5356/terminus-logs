use std::fs;
use std::path::PathBuf;

/// Recover the absolute graph path associated with the live service.
pub fn phase_b(a: &str, b: &str) -> Result<String, String> {
    let _ = a;
    let _ = b;
    let token = fs::read_to_string("/app/environment/vault/active.token")
        .map_err(|e| e.to_string())?;
    let key = token.trim();
    let path = PathBuf::from(format!("/app/environment/vault/graphs/{key}.json"));
    if !path.is_file() {
        return Err(format!("missing {}", path.display()));
    }
    Ok(path.to_string_lossy().into_owned())
}
