use std::fs;
use std::path::Path;

pub fn validate_component(path: &Path) -> Result<(), String> {
    let bytes = fs::read(path).map_err(|err| format!("read component: {err}"))?;
    if !bytes.starts_with(b"\0asm") {
        return Err("component artifact does not start with wasm magic".to_string());
    }
    if !bytes
        .windows(b"wasi:io/streams".len())
        .any(|window| window == b"wasi:io/streams")
    {
        return Err("component artifact does not mention wasi:io/streams".to_string());
    }
    Ok(())
}
