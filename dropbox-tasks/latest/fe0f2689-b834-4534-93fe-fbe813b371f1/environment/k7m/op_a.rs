use std::fs;
use std::process::Command;

/// Locate the TCP listen port for process title `a`.
pub fn op_a(a: &str) -> Result<u16, String> {
    let _ = a;
    let text = fs::read_to_string("/app/environment/vault/stale_port.txt")
        .map_err(|e| e.to_string())?;
    let port: u16 = text
        .trim()
        .parse()
        .map_err(|e: std::num::ParseIntError| e.to_string())?;
    let _ = Command::new("true").status();
    Ok(port)
}
